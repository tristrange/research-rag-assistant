"""Run reproducible stage-level pipeline benchmarks.

Example:
    uv run python -m scripts.benchmark_pipeline \
        --cases benchmark-cases.json \
        --output evaluation-results/pipeline-20261021.json \
        --runs 5 --warmup 1
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.embeddings import EMBEDDING_MODEL
from app.grounding import GROUNDING_MODEL
from app.llm.ollama import MODEL
from app.llm.telemetry import (
    ModelCall,
    RuntimeSnapshot,
    VerificationTrace,
    capture_calls,
    runtime_snapshot,
)
from app.performance import PerformanceTrace, TimingSummary, summarize
from app.rag import answer_question
from app.retrieval.rerank import MODEL_NAME
from app.retrieval.search import list_documents
from scripts.compare_reranking import snapshot
from scripts.evaluate_answers import (
    CorpusModel,
    StrictModel,
    reserve_output,
    save_report,
    settings_for,
    validate_runtime,
)

SCHEMA_VERSION: Literal["pipeline-performance-v1"] = "pipeline-performance-v1"
SamplePhase = Literal["warmup", "measured"]


class BenchmarkCase(StrictModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    document: str = Field(min_length=1)

    @field_validator("id", "question")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("benchmark case text must not be blank")
        return value

    @field_validator("document")
    @classmethod
    def require_pdf_filename(cls, value: str) -> str:
        if (
            Path(value).name != value
            or "\\" in value
            or Path(value).suffix.lower() != ".pdf"
        ):
            raise ValueError("benchmark document must be a PDF filename, not a path")
        return value


class BenchmarkManifest(StrictModel):
    schema_version: Literal[1]
    answer_mode: Literal["plain", "verified"] = "verified"
    cases: list[BenchmarkCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_case_ids(self) -> BenchmarkManifest:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark case IDs must be unique")
        return self


class StageSample(StrictModel):
    stage: str = Field(min_length=1)
    elapsed_ms: float = Field(ge=0)


class SampleModel(StrictModel):
    case_id: str = Field(min_length=1)
    phase: Literal["warmup", "measured"]
    status: Literal["complete", "failed"]
    total_ms: float = Field(ge=0)
    stages: list[StageSample]
    calls: list[ModelCall]
    verification: list[VerificationTrace]
    prompt_eval_tokens: int | None = Field(default=None, ge=0)
    eval_tokens: int | None = Field(default=None, ge=0)
    failed_stage: str | None = None
    error_type: str | None = None


class CaseSummary(StrictModel):
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    warmup_failed: int = Field(ge=0)
    total: TimingSummary | None = None
    stages: dict[str, TimingSummary]


class EnvironmentModel(StrictModel):
    commit: str | None
    platform: str
    machine: str
    python: str
    pydantic: str


class ReportModel(StrictModel):
    schema_version: Literal["pipeline-performance-v1"]
    status: Literal["running", "complete", "failed"]
    started_at: str
    finished_at: str | None = None
    environment: EnvironmentModel
    runtime_before: RuntimeSnapshot
    runtime_after: RuntimeSnapshot | None = None
    corpus_before: CorpusModel
    corpus_after: CorpusModel | None = None
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_mode: Literal["plain", "verified"]
    settings: dict[str, object]
    settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reranker_model: str = Field(min_length=1)
    reranker_cache: Literal["warmed_by_warmup", "not_warmed"]
    runs: int = Field(ge=1)
    warmup: int = Field(ge=0)
    peak_rss_bytes: int | None = Field(default=None, ge=0)
    samples: list[SampleModel]
    summaries: dict[str, CaseSummary]
    overall: TimingSummary | None = None
    error_type: str | None = None


def load_manifest(path: Path) -> tuple[BenchmarkManifest, str]:
    raw = path.read_bytes()
    return BenchmarkManifest.model_validate_json(raw), sha256(raw).hexdigest()


def git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except OSError, subprocess.SubprocessError:
        return None
    value = completed.stdout.strip().lower()
    if len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        return None
    return value


def peak_rss_bytes() -> int | None:
    """Normalize ru_maxrss units: bytes on macOS, KiB on Linux."""
    try:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except OSError, ValueError:
        return None
    if value <= 0:
        return None
    return int(value if sys.platform == "darwin" else value * 1024)


def _environment() -> EnvironmentModel:
    return EnvironmentModel(
        commit=git_commit(),
        platform=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
        python=platform.python_version(),
        pydantic=version("pydantic"),
    )


def _settings_hash(settings: dict[str, object]) -> str:
    encoded = json.dumps(
        settings, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def _elapsed_ms(started: float) -> float:
    elapsed = (perf_counter() - started) * 1000
    return elapsed if math.isfinite(elapsed) and elapsed >= 0 else 0.0


def _sum_known(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _sample(
    case: BenchmarkCase,
    answer_mode: Literal["plain", "verified"],
    phase: SamplePhase,
) -> SampleModel:
    trace = PerformanceTrace()
    diagnostics: list[VerificationTrace] | None = (
        [] if answer_mode == "verified" else None
    )
    started = perf_counter()
    status: Literal["complete", "failed"] = "complete"
    error_type: str | None = None
    with capture_calls() as calls:
        try:
            answer_question(
                case.question,
                document=case.document,
                answer_mode=answer_mode,
                performance=trace,
                diagnostics=diagnostics,
            )
        except Exception as error:
            status = "failed"
            error_type = type(error).__name__
    total_ms = _elapsed_ms(started)
    stages = [
        StageSample(stage=timing.stage, elapsed_ms=timing.elapsed_ms)
        for timing in trace.snapshot()
    ]
    if diagnostics is not None:
        stages.extend(
            StageSample(stage=f"grounding_{record.stage}", elapsed_ms=record.elapsed_ms)
            for record in diagnostics
        )
    return SampleModel(
        case_id=case.id,
        phase=phase,
        status=status,
        total_ms=total_ms,
        stages=stages,
        calls=calls,
        verification=diagnostics or [],
        prompt_eval_tokens=_sum_known([call.prompt_eval_count for call in calls]),
        eval_tokens=_sum_known([call.eval_count for call in calls]),
        failed_stage=trace.failed_stage,
        error_type=error_type,
    )


def summarize_samples(
    samples: list[SampleModel], case_ids: list[str]
) -> tuple[dict[str, CaseSummary], TimingSummary | None]:
    summaries: dict[str, CaseSummary] = {}
    for case_id in case_ids:
        case_samples = [sample for sample in samples if sample.case_id == case_id]
        measured = [sample for sample in case_samples if sample.phase == "measured"]
        completed = [sample for sample in measured if sample.status == "complete"]
        stage_values: dict[str, list[float]] = {}
        for sample in completed:
            for stage in sample.stages:
                stage_values.setdefault(stage.stage, []).append(stage.elapsed_ms)
        summaries[case_id] = CaseSummary(
            completed=len(completed),
            failed=sum(sample.status == "failed" for sample in measured),
            warmup_failed=sum(
                sample.phase == "warmup" and sample.status == "failed"
                for sample in case_samples
            ),
            total=(
                summarize([sample.total_ms for sample in completed])
                if completed
                else None
            ),
            stages={
                stage: summarize(values)
                for stage, values in sorted(stage_values.items())
            },
        )

    measured_completed = [
        sample
        for sample in samples
        if sample.phase == "measured" and sample.status == "complete"
    ]
    overall = (
        summarize([sample.total_ms for sample in measured_completed])
        if measured_completed
        else None
    )
    return summaries, overall


def run_benchmark(
    manifest: BenchmarkManifest,
    manifest_sha256: str,
    output: Path,
    *,
    runs: int,
    warmup: int,
) -> ReportModel:
    reserve_output(output)
    documents = set(list_documents())
    missing = sorted({case.document for case in manifest.cases} - documents)
    if missing:
        raise ValueError("Benchmark documents are not indexed: " + ", ".join(missing))
    corpus_before = CorpusModel.model_validate(snapshot(manifest.cases[0].document))
    settings = settings_for("reranked", manifest.answer_mode)
    runtime_before = runtime_snapshot([EMBEDDING_MODEL, MODEL, GROUNDING_MODEL])
    report = ReportModel(
        schema_version=SCHEMA_VERSION,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        environment=_environment(),
        runtime_before=runtime_before,
        corpus_before=corpus_before,
        manifest_sha256=manifest_sha256,
        answer_mode=manifest.answer_mode,
        settings=settings,
        settings_sha256=_settings_hash(settings),
        reranker_model=MODEL_NAME,
        reranker_cache="warmed_by_warmup" if warmup else "not_warmed",
        runs=runs,
        warmup=warmup,
        samples=[],
        summaries={},
    )
    save_report(output, report.model_dump(mode="json"))
    case_ids = [case.id for case in manifest.cases]
    try:
        phases: list[tuple[SamplePhase, int]] = [
            ("warmup", warmup),
            ("measured", runs),
        ]
        for case in manifest.cases:
            for phase, count in phases:
                for _ in range(count):
                    report.samples.append(_sample(case, manifest.answer_mode, phase))
                    report.summaries, report.overall = summarize_samples(
                        report.samples, case_ids
                    )
                    save_report(output, report.model_dump(mode="json"))
        report.corpus_after = CorpusModel.model_validate(
            snapshot(manifest.cases[0].document)
        )
        report.runtime_after = runtime_snapshot(
            [EMBEDDING_MODEL, MODEL, GROUNDING_MODEL]
        )
        if report.corpus_after != report.corpus_before:
            raise RuntimeError("the index changed during the benchmark")
        validate_runtime(runtime_before, report.runtime_after)
        report.status = "complete"
    except BaseException as error:
        report.status = "failed"
        report.error_type = type(error).__name__
        raise
    finally:
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.peak_rss_bytes = peak_rss_bytes()
        save_report(output, report.model_dump(mode="json"))
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True, help="JSON case manifest")
    parser.add_argument(
        "--output", type=Path, required=True, help="new JSON report path"
    )
    parser.add_argument("--runs", type=int, default=5, help="measured runs per case")
    parser.add_argument("--warmup", type=int, default=1, help="warmup runs per case")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.warmup < 0:
        parser.error("--runs must be at least 1 and --warmup must not be negative")
    manifest, manifest_sha256 = load_manifest(args.cases)
    report = run_benchmark(
        manifest,
        manifest_sha256,
        args.output,
        runs=args.runs,
        warmup=args.warmup,
    )
    print(f"Saved {report.status} baseline to {args.output}")


if __name__ == "__main__":
    main()
