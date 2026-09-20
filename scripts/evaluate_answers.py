"""Run end-to-end answer evaluation: uv run python -m scripts.evaluate_answers."""

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
from tempfile import NamedTemporaryFile
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select

from app.answer_evaluation import (
    AnswerEvaluationCase, CaseEvaluation, GeneratedCaseAnswer, JudgeScores, EXACT_REFUSALS,
    evidence_found, generate_case_answer, judge_case_answer, judge_prompt, abstention_prompt, summarize,
)
from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import EMBEDDING_MODEL
from app.ingestion.pdf import extract_pages
from app.grounding import (
    DRAFT_THINK, VERIFIER_THINK, GROUNDING_MODEL, GROUNDING_CONTEXT_TOKENS, GROUNDING_OUTPUT_TOKENS,
    grounding_fingerprint,
)
from app.judge_calibration import CALIBRATION_VERSION, run_calibration
from app.llm.ollama import JUDGE_THINK, JUDGE_MODEL, MODEL, Thinking, generate_json
from app.retrieval import CANDIDATE_COUNT, default_top_k
from app.retrieval.context import MAX_CONTEXT_CHARS, NEIGHBOR_RADIUS, render_context
from app.prompts import answer_prompt
from app.types import AnswerResult, ChunkData, PageData
from scripts.answer_quality_cases import ANSWER_CASES, PAPER_SHA256
from scripts.compare_reranking import CorpusSnapshot, snapshot


SCHEMA_VERSION = 2
EVALUATOR_VERSION = "9"


def _prompt_fingerprint() -> str:
    case = AnswerEvaluationCase(
        id="prompt-fingerprint", question="Question?", answerable=True,
        reference_answer="Reference.",
        evidence=[{"document": "paper.pdf", "page": 1, "quote": "Evidence."}],
    )
    result = AnswerResult(
        answer="Answer.",
        sources=[ChunkData(document="paper.pdf", page=1, chunk_index=0, text="Evidence.")],
    )
    return sha256((abstention_prompt(case["question"], result["answer"]) + "\n" + judge_prompt(case, result) + "\n" + json.dumps(sorted(EXACT_REFUSALS))).encode()).hexdigest()


EVALUATOR_PROMPT_SHA256 = _prompt_fingerprint()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class EvidenceModel(StrictModel):
    document: str = Field(min_length=1)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)


class CaseModel(StrictModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answerable: bool
    reference_answer: str = Field(min_length=1)
    evidence: list[EvidenceModel]


class BenchmarkMetadata(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    doi: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    license: str = Field(min_length=1)
    license_url: str = Field(min_length=1)
    split: Literal["development", "holdout"]
    document: str = Field(min_length=1)
    paper_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_document(self) -> "BenchmarkMetadata":
        if Path(self.document).name != self.document or "\\" in self.document:
            raise ValueError("benchmark document must be a filename, not a path")
        if Path(self.document).suffix.lower() != ".pdf":
            raise ValueError("benchmark document must name a PDF")
        return self


class BenchmarkManifest(StrictModel):
    schema_version: Literal[1]
    metadata: BenchmarkMetadata
    cases: list[CaseModel] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self) -> "BenchmarkManifest":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark case IDs must be unique")
        for case in self.cases:
            if case.answerable != bool(case.evidence):
                raise ValueError("only answerable cases must have evidence labels")
            if any(label.document != self.metadata.document for label in case.evidence):
                raise ValueError("evidence must refer to the benchmark document")
        return self


def load_benchmark(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate_json(path.read_text(encoding="utf-8"))


class SourceModel(StrictModel):
    document: str = Field(min_length=1)
    page: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    section: str = "unknown"


class GeneratedAnswerModel(StrictModel):
    case: CaseModel
    answer: str
    sources: list[SourceModel]
    evidence_found: list[bool]
    evidence_recall: float | None = Field(default=None, ge=0, le=1)
    answer_ms: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_evidence_shape(self) -> "GeneratedAnswerModel":
        if len(self.evidence_found) != len(self.case.evidence):
            raise ValueError("evidence_found must correspond to every evidence label")
        expected = sum(self.evidence_found) / len(self.evidence_found) if self.evidence_found else None
        if self.evidence_recall != expected:
            raise ValueError("evidence_recall does not match evidence_found")
        return self


class StoredJudgeModel(StrictModel):
    correctness: int = Field(ge=0, le=2)
    completeness: int = Field(ge=0, le=2)
    citation_support: int = Field(ge=0, le=2)
    explanation: str = Field(min_length=1)


class CompletedResultModel(GeneratedAnswerModel):
    abstained: bool
    judge: StoredJudgeModel
    judge_ms: float = Field(ge=0)
    passed: bool


class CorpusModel(StrictModel):
    sha256: str = Field(min_length=1)
    chunks_by_document: dict[str, int]


class SettingsModel(StrictModel):
    strategy: Literal["vector", "reranked", "expanded"]
    top_k: int = Field(ge=1)
    candidate_count: int = Field(ge=1)
    answer_mode: Literal["plain", "verified"]
    verifier_model: str | None
    verifier_temperature: float | None
    verifier_think: Thinking | None
    grounding_context_tokens: int | None = Field(default=None, ge=1)
    grounding_output_tokens: int | None = Field(default=None, ge=1)
    generator_prompt_sha256: str
    generator_temperature: str
    generator_think: str
    judge_temperature: float
    judge_think: bool
    neighbor_radius: int = Field(ge=0)
    max_context_chars: int | None = Field(default=None, ge=1)


class EnvironmentModel(StrictModel):
    python: str
    platform: str
    pydantic: str
    sentence_transformers: str


class CalibrationResultModel(StrictModel):
    id: str = Field(min_length=1)
    passed: bool
    expected: dict[str, list[int] | bool]
    actual: JudgeScores


class CalibrationModel(StrictModel):
    version: str = Field(min_length=1)
    passed: bool
    results: list[CalibrationResultModel]

    @model_validator(mode="after")
    def validate_results(self) -> "CalibrationModel":
        ids = [result.id for result in self.results]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("calibration results must have unique IDs and must not be empty")
        if self.passed != all(result.passed for result in self.results):
            raise ValueError("calibration passed flag does not match its results")
        return self


class MetricsModel(StrictModel):
    cases: int = Field(ge=1)
    answerable_cases: int = Field(ge=0)
    unanswerable_cases: int = Field(ge=0)
    correctness: float | None = Field(default=None, ge=0, le=1)
    completeness: float | None = Field(default=None, ge=0, le=1)
    citation_support: float | None = Field(default=None, ge=0, le=1)
    evidence_hit_rate: float | None = Field(default=None, ge=0, le=1)
    mean_evidence_recall: float | None = Field(default=None, ge=0, le=1)
    abstention_accuracy: float = Field(ge=0, le=1)
    unanswerable_abstention_rate: float | None = Field(default=None, ge=0, le=1)
    answerable_false_abstention_rate: float | None = Field(default=None, ge=0, le=1)
    pass_rate: float = Field(ge=0, le=1)
    mean_answer_ms: float = Field(ge=0)
    mean_judge_ms: float = Field(ge=0)


class ReportModel(StrictModel):
    schema_version: Literal[2]
    status: Literal["running", "failed", "calibration_failed", "complete"]
    started_at: str
    finished_at: str | None = None
    resumed_from: str | None = None
    error: str | None = None
    corpus: CorpusModel
    paper_sha256: str
    benchmark: BenchmarkMetadata | None = None
    cases_sha256: str
    generator_model: str
    judge_model: str
    embedding_model: str
    reranker_model: str | None
    settings: SettingsModel
    evaluator_version: str
    evaluator_prompt_sha256: str
    calibration_version: str
    calibration: CalibrationModel | None
    environment: EnvironmentModel
    methodology: str
    requested_case_ids: list[str]
    metrics: MetricsModel | None
    results: list[CompletedResultModel]
    pending: GeneratedAnswerModel | None

    @model_validator(mode="after")
    def validate_run_shape(self) -> "ReportModel":
        result_ids = [result.case.id for result in self.results]
        if not self.requested_case_ids or len(self.requested_case_ids) != len(set(self.requested_case_ids)):
            raise ValueError("requested case IDs must be unique and must not be empty")
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("completed result IDs must not contain duplicates")
        if result_ids != self.requested_case_ids[:len(result_ids)]:
            raise ValueError("completed results must be an ordered prefix of requested cases")
        if self.pending is not None:
            if len(self.results) >= len(self.requested_case_ids):
                raise ValueError("a completed run cannot contain a pending answer")
            if self.pending.case.id != self.requested_case_ids[len(self.results)]:
                raise ValueError("pending answer must be for the next requested case")
        if self.metrics is not None and self.status != "complete":
            raise ValueError("aggregate metrics are only valid for a complete run")
        if self.calibration is not None and self.calibration.version != self.calibration_version:
            raise ValueError("calibration result version does not match calibration_version")
        if self.status == "complete":
            if len(self.results) != len(self.requested_case_ids) or self.pending is not None:
                raise ValueError("a complete run must contain every requested result")
            if self.calibration is None or not self.calibration.passed or self.metrics is None:
                raise ValueError("a complete run requires passed calibration and aggregate metrics")
        return self


def indexed_sources() -> list[ChunkData]:
    with SessionLocal() as db:
        return [
            ChunkData(document=c.document, page=c.page, chunk_index=c.chunk_index, text=c.text, section=c.section)
            for c in db.scalars(select(Chunk).order_by(Chunk.id))
        ]


def validate_labels(cases: list[AnswerEvaluationCase], pages: list[PageData]) -> None:
    """Validate references against the PDF, independently of chunk boundaries."""
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Cases must have unique IDs and must not be empty")
    full_pages = [ChunkData(**page, chunk_index=0) for page in pages]
    for case in cases:
        if not case["id"] or not case["question"].strip() or not case["reference_answer"].strip():
            raise ValueError("Each case needs an ID, question, and reference answer")
        if case["answerable"] != bool(case["evidence"]):
            raise ValueError(f"{case['id']}: only answerable cases must have evidence labels")
        for label in case["evidence"]:
            if not evidence_found(label, full_pages):
                raise ValueError(f"{case['id']}: evidence quote is absent from the labelled PDF page")


def validate_index(sources: list[ChunkData], pages: list[PageData]) -> None:
    page_text = {(p["document"], p["page"]): p["text"] for p in pages}
    for source in sources:
        text = page_text.get((source["document"], source["page"]), "")
        if not source["text"].strip() or source["text"] not in text:
            raise ValueError("The index contains text from another PDF or extraction; reindex the evaluation paper")


def print_result(result: CaseEvaluation) -> None:
    scores = result["judge"]
    status = "PASS" if result["passed"] else "FAIL"
    print(f"[{status}] {result['case']['id']} | correctness {scores['correctness']}/2, "
          f"completeness {scores['completeness']}/2, source support {scores['citation_support']}/2, "
          f"abstained={result['abstained']}", flush=True)


def reserve_output(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.open("x", encoding="utf-8").close()
    except FileExistsError as error:
        raise ValueError(f"Report already exists: {output}. Choose a new path.") from error


def save_report(output: Path, report: Mapping[str, object]) -> None:
    """Atomically checkpoint a report after its output path has been reserved."""
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_report(path: Path) -> ReportModel:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot resume from {path}: invalid JSON report ({error})") from error
    if not isinstance(raw, dict):
        raise ValueError(f"Cannot resume from {path}: report must be a JSON object")
    if raw.get("schema_version") == 1:
        raise ValueError(
            "Cannot resume schema version 1 reports: they did not save pending generated answers "
            "or enough evaluator configuration. Start a new evaluation instead."
        )
    try:
        return ReportModel.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"Cannot resume from {path}: invalid report structure: {error}") from error


def cases_hash(cases: list[AnswerEvaluationCase]) -> str:
    return sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()


def settings_for(strategy: str, answer_mode: str = "plain", top_k: int | None = None) -> dict[str, object]:
    top_k = default_top_k(strategy == "expanded") if top_k is None else top_k
    return {
        "strategy": strategy, "top_k": top_k,
        "answer_mode": answer_mode,
        "verifier_model": GROUNDING_MODEL if answer_mode == "verified" else None,
        "verifier_temperature": 0.0 if answer_mode == "verified" else None,
        "verifier_think": VERIFIER_THINK if answer_mode == "verified" else None,
        "grounding_context_tokens": GROUNDING_CONTEXT_TOKENS if answer_mode == "verified" else None,
        "grounding_output_tokens": GROUNDING_OUTPUT_TOKENS if answer_mode == "verified" else None,
        "candidate_count": top_k if strategy == "vector" else max(CANDIDATE_COUNT, top_k),
        "generator_prompt_sha256": grounding_fingerprint() if answer_mode == "verified" else sha256(answer_prompt("Question?", render_context([ChunkData(
            document="paper.pdf", page=1, chunk_index=0, text="Evidence.", section="references",
        )])).encode()).hexdigest(),
        "generator_temperature": "0.0" if answer_mode == "verified" else "model default",
        "generator_think": str(DRAFT_THINK).lower() if answer_mode == "verified" else "model default",
        "judge_temperature": 0.0, "judge_think": JUDGE_THINK,
        "neighbor_radius": NEIGHBOR_RADIUS if strategy == "expanded" else 0,
        "max_context_chars": MAX_CONTEXT_CHARS if strategy == "expanded" else None,
    }


def validate_resume_consistency(
    saved: ReportModel,
    cases: list[AnswerEvaluationCase],
    corpus: CorpusSnapshot,
    strategy: str,
    reranker_model: str | None,
    answer_mode: str = "plain",
    *, paper_sha256: str | None = None, benchmark: BenchmarkMetadata | None = None,
    top_k: int | None = None,
) -> None:
    expected: dict[str, tuple[object, object]] = {
        "corpus": (saved.corpus.model_dump(), corpus),
        "paper SHA-256": (saved.paper_sha256, paper_sha256 or PAPER_SHA256),
        "benchmark": (saved.benchmark, benchmark),
        "cases": (saved.cases_sha256, cases_hash(cases)),
        "generator model": (saved.generator_model, GROUNDING_MODEL if answer_mode == "verified" else MODEL),
        "judge model": (saved.judge_model, JUDGE_MODEL),
        "embedding model": (saved.embedding_model, EMBEDDING_MODEL),
        "reranker model": (saved.reranker_model, reranker_model),
        "settings": (saved.settings.model_dump(), settings_for(strategy, answer_mode, top_k)),
        "evaluator version": (saved.evaluator_version, EVALUATOR_VERSION),
        "evaluator prompt": (saved.evaluator_prompt_sha256, EVALUATOR_PROMPT_SHA256),
    }
    mismatches = [name for name, (actual, wanted) in expected.items() if actual != wanted]
    if mismatches:
        raise ValueError("Cannot resume because the following changed: " + ", ".join(mismatches))
    if saved.calibration_version != CALIBRATION_VERSION:
        raise ValueError("Cannot resume because the judge calibration version changed")
    current_cases = {case["id"]: case for case in cases}
    for completed in saved.results:
        if completed.case.model_dump() != current_cases[completed.case.id]:
            raise ValueError(f"Cannot resume because case {completed.case.id!r} changed")
    if saved.pending is not None and saved.pending.case.model_dump() != current_cases[saved.pending.case.id]:
        raise ValueError(f"Cannot resume because pending case {saved.pending.case.id!r} changed")


def _new_report(
    now: datetime, before: CorpusSnapshot, cases: list[AnswerEvaluationCase],
    strategy: str, reranker_model: str | None, answer_mode: str = "plain",
    *, paper_sha256: str | None = None, benchmark: BenchmarkMetadata | None = None,
    top_k: int | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION, "status": "running", "started_at": now.isoformat(),
        "finished_at": None, "resumed_from": None, "error": None, "corpus": before,
        "paper_sha256": paper_sha256 or PAPER_SHA256, "cases_sha256": cases_hash(cases),
        "benchmark": benchmark.model_dump() if benchmark else None,
        "generator_model": GROUNDING_MODEL if answer_mode == "verified" else MODEL, "judge_model": JUDGE_MODEL, "embedding_model": EMBEDDING_MODEL,
        "reranker_model": reranker_model, "settings": settings_for(strategy, answer_mode, top_k),
        "evaluator_version": EVALUATOR_VERSION, "evaluator_prompt_sha256": EVALUATOR_PROMPT_SHA256,
        "calibration_version": CALIBRATION_VERSION, "calibration": None,
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "pydantic": version("pydantic"), "sentence_transformers": version("sentence-transformers"),
        },
        "methodology": (
            "Assistant-authored reference labels; the built-in sample is a development set. "
            "External benchmark split and provenance are recorded in benchmark metadata. "
            "A holdout label alone does not establish independence; do not tune on its results. "
            "Labels are not independently reviewed. Evidence quotes are "
            "validated against the PDF; a hit requires the full normalized quote in a single returned chunk. "
            "This may undercount alternate or split evidence. Exact fact-free refusal sentences are scored "
            "deterministically; other responses use separate reference-blind abstention and factual "
            "grading calls to the recorded judge model. Answerable refusals receive zero correctness "
            "and completeness in code. Judge timing includes both calls. Inspect explanations "
            "and passages manually; model judging is not independent human validation. "
            "Source support measures the returned passage bundle, not inline citation attribution. "
            "Correctness, completeness, and support averages cover answerable cases only. "
            "Calibration may warm the model; there is no dedicated timing warmup. "
            "Answer timings include any model loading, retrieval, and generation; judge "
            "timings are separate. Generation runs once per case with the recorded answer-mode settings. Verified mode includes drafting, verification and at most one correction attempt in answer timings."
        ),
        "requested_case_ids": [case["id"] for case in cases],
        "metrics": None, "results": [], "pending": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate answers, returned evidence, and abstention with a local model judge."
    )
    parser.add_argument("--output", type=Path,
                        help="new JSON report path; defaults to evaluation-results/answers-TIMESTAMP.json")
    parser.add_argument("--resume", type=Path,
                        help="resume a schema-v2 report into a new output without changing the original")
    parser.add_argument("--benchmark", type=Path, help="JSON benchmark manifest; omit for the legacy sample development set")
    parser.add_argument("--pdf", type=Path, help="local PDF; required with --benchmark, otherwise defaults to data/sample.pdf")
    parser.add_argument("--validate-only", action="store_true", help="check PDF fingerprint and labels without database or model calls")
    parser.add_argument("--case", dest="case_ids", action="append",
                        help="run just this case (repeat the flag to select more)")
    parser.add_argument("--strategy", choices=["vector", "reranked", "expanded"], default=None)
    parser.add_argument("--answer-mode", choices=["plain", "verified"], default=None)
    parser.add_argument("--top-k", type=int, choices=range(1, 11),
                        help="seed passages to retain (default: 6 expanded, 3 otherwise)")
    args = parser.parse_args()
    benchmark: BenchmarkMetadata | None = None
    available_cases = ANSWER_CASES
    paper_hash = PAPER_SHA256
    document = "sample.pdf"
    if args.benchmark is not None:
        if args.pdf is None:
            parser.error("--pdf is required with --benchmark")
        try:
            manifest = load_benchmark(args.benchmark)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        benchmark = manifest.metadata
        available_cases = [cast(AnswerEvaluationCase, case.model_dump()) for case in manifest.cases]
        paper_hash = benchmark.paper_sha256
        document = benchmark.document
    paper = args.pdf or Path("data/sample.pdf")
    if paper.name != document:
        parser.error(f"PDF filename must match benchmark document {document!r}")
    if args.case_ids is not None:
        if len(args.case_ids) != len(set(args.case_ids)):
            parser.error("--case selections must not contain duplicates")
        unknown = set(args.case_ids) - {c["id"] for c in available_cases}
        if unknown:
            parser.error("Unknown benchmark case IDs: " + ", ".join(sorted(unknown)))
    if args.validate_only and args.resume:
        parser.error("--validate-only cannot be combined with --resume")
    now = datetime.now(timezone.utc)
    output = args.output or Path("evaluation-results") / f"answers-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    if output.exists():
        parser.error(f"Report already exists: {output}. Choose a new path.")
    saved: ReportModel | None = None
    if args.resume is not None:
        try:
            saved = load_report(args.resume)
        except ValueError as error:
            parser.error(str(error))
        if args.case_ids is not None and args.case_ids != saved.requested_case_ids:
            parser.error("--case selections must exactly match the resumed report, in the same order")
        if args.strategy is not None and args.strategy != saved.settings.strategy:
            parser.error("--strategy must match the resumed report")
        if args.answer_mode is not None and args.answer_mode != saved.settings.answer_mode:
            parser.error("--answer-mode must match the resumed report")
        if args.top_k is not None and args.top_k != saved.settings.top_k:
            parser.error("--top-k must match the resumed report")
        top_k = saved.settings.top_k
        answer_mode = saved.settings.answer_mode
        strategy = saved.settings.strategy
        requested_ids = saved.requested_case_ids
    else:
        strategy = args.strategy or "reranked"
        top_k = args.top_k if args.top_k is not None else default_top_k(strategy == "expanded")
        answer_mode = args.answer_mode or "plain"
        selected_ids = set(args.case_ids) if args.case_ids else None
        requested_ids = [
            case["id"] for case in available_cases
            if selected_ids is None or case["id"] in selected_ids
        ]
    requested_set = set(requested_ids)
    cases = [case for case in available_cases if case["id"] in requested_set]
    if [case["id"] for case in cases] != requested_ids:
        parser.error("Requested cases no longer match the benchmark cases or their order")

    if sha256(paper.read_bytes()).hexdigest() != paper_hash:
        raise ValueError("PDF does not match the paper fingerprint in the benchmark")
    pages = extract_pages(str(paper))
    validate_labels(cases, pages)
    if args.validate_only:
        print(f"Validated {len(cases)} cases against {paper}; no database or model calls made.")
        return
    before = snapshot(document)
    if set(before["chunks_by_document"]) != {document}:
        raise ValueError("These answerability labels require an index containing only the evaluation paper")
    validate_index(indexed_sources(), pages)

    from app.rag import answer_question
    from app.retrieval.rerank import MODEL_NAME

    reranker_model = None if strategy == "vector" else MODEL_NAME
    if saved is None:
        report = ReportModel.model_validate(
            _new_report(now, before, cases, strategy, reranker_model, answer_mode,
                        paper_sha256=paper_hash, benchmark=benchmark, top_k=top_k)
        ).model_dump()
    else:
        validate_resume_consistency(saved, cases, before, strategy, reranker_model, answer_mode,
                                    paper_sha256=paper_hash, benchmark=benchmark, top_k=top_k)
        report = cast(dict[str, object], saved.model_dump())
        report = {
            **report,
            "status": "running", "finished_at": None, "resumed_from": str(args.resume),
            "error": None, "metrics": None, "calibration": None,
        }

    try:
        reserve_output(output)
    except ValueError as error:
        parser.error(str(error))
    save_report(output, report)
    try:
        print("Checking the judge against known calibration examples...", flush=True)
        calibration = CalibrationModel.model_validate(run_calibration(generate_json)).model_dump()
        report = {**report, "calibration": calibration}
        save_report(output, report)
        if not calibration["passed"]:
            report = {
                **report,
                "status": "calibration_failed",
                "error": "Judge calibration failed; benchmark answers were not evaluated",
            }
            raise SystemExit(report["error"])

        answer = partial(answer_question, limit=top_k, use_reranking=strategy != "vector",
                         expand_context=strategy == "expanded", answer_mode=answer_mode)
        for index in range(len(cast(list[CaseEvaluation], report["results"])), len(cases)):
            case = cases[index]
            print(f"Evaluating {index + 1}/{len(cases)}: {case['id']}...", flush=True)
            pending = cast(GeneratedCaseAnswer | None, report["pending"])
            if pending is None:
                pending = generate_case_answer(case, answer)
                report = {**report, "pending": pending}
                save_report(output, report)
            result = judge_case_answer(pending, generate_json)
            results = [*cast(list[CaseEvaluation], report["results"]), result]
            report = {**report, "results": results, "pending": None}
            save_report(output, report)
            print_result(result)
        if snapshot(document) != before:
            raise RuntimeError("The index changed during evaluation; results are invalid")
        results = cast(list[CaseEvaluation], report["results"])
        report = {**report, "metrics": summarize(results), "status": "complete"}
    except (Exception, KeyboardInterrupt) as error:
        report = {
            **report,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "metrics": None,
        }
        raise
    finally:
        report = {**report, "finished_at": datetime.now(timezone.utc).isoformat()}
        save_report(output, report)
        print(f"Saved {report['status']} report: {output}", flush=True)
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
