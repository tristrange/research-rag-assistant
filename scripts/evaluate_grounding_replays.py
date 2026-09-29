"""Score completed fixed-source replays without generating new answers."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, cast

import httpx
from pydantic import Field, model_validator

from app.answer_evaluation import (
    AnswerEvaluationCase, CaseEvaluation, GeneratedCaseAnswer,
    evidence_found, judge_case_answer, summarize,
)
from app.judge_calibration import CALIBRATION_VERSION, run_calibration
from app.llm.ollama import JUDGE_MODEL, JUDGE_THINK, Thinking, generate_json
from app.types import ChunkData
from scripts.evaluate_answers import (
    CaseModel, CorpusModel, EVALUATOR_PROMPT_SHA256, ReportModel, SettingsModel,
    SourceModel, StrictModel, reserve_output, save_report,
)
from scripts.prepare_human_review import ReviewManifest, configuration_hash, review_set_hash


class ReplayCase(StrictModel):
    case: CaseModel
    sources: list[SourceModel]
    trace: list[dict[str, object]]
    answer: str
    elapsed_ms: float = Field(ge=0)


class CompletedReplay(StrictModel):
    status: Literal["complete"]
    started_at: str
    finished_at: str
    source_report: str
    corpus: CorpusModel
    settings: SettingsModel
    methodology: str
    results: list[ReplayCase] = Field(min_length=1)


class CandidateConfig(StrictModel):
    model: str = Field(min_length=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_think: Thinking
    verifier_think: Thinking
    grounding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ComparisonProtocol(StrictModel):
    schema_version: Literal[1]
    review_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ollama_version: str
    judge_model: str
    judge_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    grounding_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: list[CandidateConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_candidates(self) -> "ComparisonProtocol":
        names = [item.model for item in self.candidates]
        if len(names) != len(set(names)):
            raise ValueError("candidate models must be unique")
        return self


def validate_run_metadata(
    path: Path, protocol: ComparisonProtocol, settings: SettingsModel,
    provenance: list[dict[str, object]],
) -> dict[str, object]:
    """Bind scoring to the retained generation orchestrator's identity checks."""
    raw = path.read_bytes()
    record = json.loads(raw)
    candidate = next(item for item in protocol.candidates if item.model == settings.verifier_model)
    if (record.get("status") != "complete"
            or record.get("server_version", {}).get("version") != protocol.ollama_version
            or not any(item.get("name") == candidate.model and item.get("digest") == candidate.digest
                       for item in record.get("models", []))):
        raise ValueError("generation record does not attest the frozen model/runtime")
    grounding_path = Path(__file__).resolve().parents[1] / "app/grounding.py"
    if (record.get("grounding_code_sha256") != protocol.grounding_code_sha256
            or sha256(grounding_path.read_bytes()).hexdigest() != protocol.grounding_code_sha256):
        raise ValueError("generation record used a different grounding implementation")
    for item in provenance:
        matches = [step for step in record.get("steps", [])
                   if Path(step.get("report", "")).resolve() == Path(str(item["replay"])).resolve()]
        if len(matches) != 1 or matches[0].get("returncode") != 0:
            raise ValueError("generation record does not contain this successful replay")
    return {"path": str(path), "sha256": sha256(raw).hexdigest(),
            "methodology": "Orchestrator recorded identities and checked digest before each replay "
                           "and after each arm; replay bytes are separately hashed in inputs."}


def judge_runtime(protocol: ComparisonProtocol) -> dict[str, str]:
    """Check the installed judge identity and runtime before making grading calls."""
    version = httpx.get("http://localhost:11434/api/version", timeout=10.0)
    version.raise_for_status()
    tags = httpx.get("http://localhost:11434/api/tags", timeout=10.0)
    tags.raise_for_status()
    if version.json().get("version") != protocol.ollama_version or not any(
        item.get("name") == protocol.judge_model and item.get("digest") == protocol.judge_digest
        for item in tags.json().get("models", [])
    ):
        raise ValueError("installed judge/runtime differs from the frozen protocol")
    return {"ollama_version": protocol.ollama_version, "judge_digest": protocol.judge_digest}


def load_inputs(
    manifest: ReviewManifest, root: Path, paths: list[Path],
    *, protocol: ComparisonProtocol,
) -> tuple[list[GeneratedCaseAnswer], list[dict[str, object]], SettingsModel]:
    """Require the complete frozen selection, original labels, and exact passages."""
    if protocol.review_set_sha256 != review_set_hash(manifest):
        raise ValueError("comparison protocol names a different frozen selection")
    selections = {(root / item.report).resolve(): item for item in manifest.selections}
    seen: set[Path] = set()
    generated: list[GeneratedCaseAnswer] = []
    provenance: list[dict[str, object]] = []
    settings: SettingsModel | None = None
    for path in paths:
        replay_bytes = path.read_bytes()
        replay = CompletedReplay.model_validate_json(replay_bytes)
        source_path = (root / replay.source_report).resolve()
        if source_path not in selections or source_path in seen:
            raise ValueError("replays must cover each frozen source report exactly once")
        seen.add(source_path)
        selection = selections[source_path]
        source_bytes = source_path.read_bytes()
        if sha256(source_bytes).hexdigest() != selection.sha256:
            raise ValueError("frozen source report hash changed")
        source = ReportModel.model_validate_json(source_bytes)
        if source.status != "complete" or configuration_hash(source) != manifest.configuration_sha256:
            raise ValueError("source report does not match the frozen configuration")
        if replay.corpus != source.corpus:
            raise ValueError("replay corpus differs from source report")
        if replay.settings.answer_mode != "verified":
            raise ValueError("only verified replays can be compared")
        candidate = next((item for item in protocol.candidates
                          if item.model == replay.settings.verifier_model), None)
        if candidate is None or (
            replay.settings.verifier_think != candidate.verifier_think
            or replay.settings.generator_think != str(candidate.draft_think).lower()
            or replay.settings.generator_prompt_sha256 != candidate.grounding_sha256
        ):
            raise ValueError("replay does not match a frozen candidate configuration")
        # Changing a model's thinking controls is allowed; retrieval and budgets stay fixed.
        mutable = {"verifier_model", "verifier_think", "generator_think", "generator_prompt_sha256"}
        for key, value in source.settings.model_dump().items():
            if key not in mutable and replay.settings.model_dump()[key] != value:
                raise ValueError(f"replay changed frozen setting: {key}")
        if settings is not None and settings != replay.settings:
            raise ValueError("all replays in an arm must use identical model settings")
        settings = replay.settings
        selected = [item for item in source.results if item.case.id in selection.case_ids]
        if [item.case.id for item in replay.results] != [item.case.id for item in selected]:
            raise ValueError("replay case order or coverage differs from frozen selection")
        for item, original in zip(replay.results, selected, strict=True):
            if item.case != original.case or item.sources != original.sources:
                raise ValueError("replay changed a question, label, or source passage")
            case = cast(AnswerEvaluationCase, item.case.model_dump())
            case["id"] = f"{selection.id}/{case['id']}"
            sources = [cast(ChunkData, passage.model_dump()) for passage in item.sources]
            found = [evidence_found(label, sources) for label in case["evidence"]]
            generated.append(GeneratedCaseAnswer(
                case=case, answer=item.answer, sources=sources,
                evidence_found=found, evidence_recall=sum(found) / len(found) if found else None,
                answer_ms=item.elapsed_ms,
            ))
        provenance.append({
            "replay": str(path), "sha256": sha256(replay_bytes).hexdigest(),
            "source_report": selection.report, "source_report_sha256": selection.sha256,
            "paper_sha256": source.paper_sha256, "corpus": source.corpus.model_dump(),
        })
    if seen != set(selections) or settings is None:
        raise ValueError("replays do not cover every frozen paper")
    # Canonical paper order prevents accidental differences between grading arms.
    order = {f"{item.id}/{case_id}": index for index, (item, case_id) in enumerate(
        (item, case_id) for item in manifest.selections for case_id in item.case_ids
    )}
    generated.sort(key=lambda item: order[item["case"]["id"]])
    return generated, provenance, settings


def evaluate(
    manifest: ReviewManifest, root: Path, paths: list[Path], output: Path,
    *, protocol: ComparisonProtocol, generation_record: Path,
) -> None:
    if JUDGE_MODEL != protocol.judge_model or JUDGE_THINK is not False:
        raise ValueError("judge differs from the frozen comparison protocol")
    generated, provenance, settings = load_inputs(manifest, root, paths, protocol=protocol)
    attestation = validate_run_metadata(generation_record, protocol, settings, provenance)
    runtime = judge_runtime(protocol)
    reserve_output(output)
    results: list[CaseEvaluation] = []
    report: dict[str, object] = {
        "status": "running", "error": None, "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol": protocol.model_dump(),
        "generation_record": attestation, "judge_runtime": runtime,
        "review_set_sha256": review_set_hash(manifest), "inputs": provenance,
        "settings": settings.model_dump(), "judge_model": JUDGE_MODEL,
        "judge_think": JUDGE_THINK, "judge_temperature": 0.0,
        "evaluator_prompt_sha256": EVALUATOR_PROMPT_SHA256,
        "calibration_version": CALIBRATION_VERSION, "calibration": None,
        "requested_case_ids": [item["case"]["id"] for item in generated],
        "results": results, "metrics": None,
        "methodology": "Saved answers only; no generation or retrieval. Fixed judge and inspected "
                       "development labels, not independent human review. Answer timing excludes retrieval.",
    }
    save_report(output, report)
    try:
        calibration = run_calibration(generate_json)
        report["calibration"] = calibration
        save_report(output, report)
        if not calibration["passed"]:
            report["status"] = "calibration_failed"
            report["error"] = "Judge calibration failed"
            raise SystemExit("Judge calibration failed; no answer metrics published")
        for item in generated:
            result = judge_case_answer(item, generate_json)
            results.append(result)
            save_report(output, report)
            print(f"Judged {item['case']['id']}: abstained={result['abstained']}", flush=True)
        if judge_runtime(protocol) != runtime:
            raise ValueError("judge/runtime changed while grading")
        report["metrics"] = summarize(results)
        report["status"] = "complete"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(output, report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", type=Path, nargs="+")
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/v1-development-review.json"))
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/verified-model-comparison.json"))
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--generation-record", type=Path, required=True,
                        help="retained generation orchestration record with identity checks")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = ReviewManifest.model_validate_json(args.manifest.read_bytes())
    protocol = ComparisonProtocol.model_validate_json(args.protocol.read_bytes())
    evaluate(manifest, args.source_root, args.replays, args.output, protocol=protocol,
             generation_record=args.generation_record)


if __name__ == "__main__":
    main()
