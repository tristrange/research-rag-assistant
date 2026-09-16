"""Run end-to-end answer evaluation: uv run python -m scripts.evaluate_answers."""

import argparse
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
from typing import TextIO

from sqlalchemy import select

from app.answer_evaluation import (
    AnswerEvaluationCase, CaseEvaluation, evaluate_case, evidence_found, summarize,
)
from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import EMBEDDING_MODEL
from app.ingestion.pdf import extract_pages
from app.llm.ollama import MODEL, generate_json
from app.types import ChunkData, PageData
from scripts.answer_quality_cases import ANSWER_CASES, PAPER_SHA256
from scripts.compare_reranking import snapshot


def indexed_sources() -> list[ChunkData]:
    with SessionLocal() as db:
        return [
            ChunkData(document=c.document, page=c.page, chunk_index=c.chunk_index, text=c.text)
            for c in db.scalars(select(Chunk).order_by(Chunk.id))
        ]


def validate_labels(cases: list[AnswerEvaluationCase], pages: list[PageData]) -> None:
    """Validate references against the PDF, independently of chunk boundaries."""
    if not cases or len({c['id'] for c in cases}) != len(cases):
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


def save_report(stream: TextIO, report: dict[str, object]) -> None:
    """Checkpoint the run after each question into its exclusively created file."""
    stream.seek(0)
    json.dump(report, stream, indent=2, ensure_ascii=False)
    stream.write("\n")
    stream.truncate()
    stream.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate answers, returned evidence, and abstention with a local model judge.")
    parser.add_argument("--output", type=Path, help="JSON report path; defaults to evaluation-results/answers-TIMESTAMP.json")
    parser.add_argument("--case", dest="case_ids", action="append", choices=[c["id"] for c in ANSWER_CASES],
                        help="Run just this case (repeat the flag to select more)")
    parser.add_argument("--strategy", choices=["vector", "reranked"], default="reranked")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = args.output or Path("evaluation-results") / f"answers-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    if output.exists():
        parser.error(f"Report already exists: {output}. Choose a new path.")
    cases = [c for c in ANSWER_CASES if not args.case_ids or c["id"] in args.case_ids]
    paper = Path("data/sample.pdf")
    if sha256(paper.read_bytes()).hexdigest() != PAPER_SHA256:
        raise ValueError("data/sample.pdf does not match the paper these reference labels describe")
    pages = extract_pages(str(paper))
    validate_labels(cases, pages)
    before = snapshot("sample.pdf")
    if set(before["chunks_by_document"]) != {"sample.pdf"}:
        raise ValueError("These answerability labels require an index containing only the evaluation paper")
    validate_index(indexed_sources(), pages)

    from app.rag import answer_question
    from app.retrieval.rerank import MODEL_NAME

    results: list[CaseEvaluation] = []
    report: dict[str, object] = {
        "schema_version": 1, "status": "running", "started_at": now.isoformat(),
        "corpus": before, "paper_sha256": PAPER_SHA256,
        "cases_sha256": sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "generator_model": MODEL, "judge_model": MODEL, "embedding_model": EMBEDDING_MODEL,
        "reranker_model": MODEL_NAME if args.strategy == "reranked" else None,
        "settings": {"strategy": args.strategy, "top_k": 3,
                     "candidate_count": 10 if args.strategy == "reranked" else 3,
                     "generator_temperature": "model default", "judge_temperature": 0.0},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "pydantic": version("pydantic"), "sentence_transformers": version("sentence-transformers")},
        "methodology": (
            "Assistant-authored reference labels on the same paper as the retrieval development set; "
            "not independently reviewed or suitable for a generalization claim. Evidence quotes are "
            "validated against the PDF; a hit requires the full normalized quote in a single returned chunk. "
            "This may undercount alternate or split evidence. Semantic scores and abstention are judged "
            "by the same model that generated the answer; inspect explanations and passages manually. "
            "Source support measures the returned passage bundle, not inline citation attribution. "
            "Correctness, completeness, and support averages cover answerable cases only. "
            "No warmup: answer timings include any model loading, retrieval, and generation; judge "
            "timings are separate. Generation is sampled once with its existing default settings."
        ),
        "requested_case_ids": [c["id"] for c in cases], "metrics": None, "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve before calling expensive model services, and preserve partial results on failure.
    with output.open("x", encoding="utf-8") as stream:
        save_report(stream, report)
        try:
            answer = partial(answer_question, use_reranking=args.strategy == "reranked")
            for index, case in enumerate(cases, 1):
                print(f"Evaluating {index}/{len(cases)}: {case['id']}...", flush=True)
                result = evaluate_case(case, answer, generate_json)
                results.append(result)
                save_report(stream, report)
                print_result(result)
            if snapshot("sample.pdf") != before:
                raise RuntimeError("The index changed during evaluation; results are invalid")
            report["metrics"] = summarize(results)
            report["status"] = "complete"
        except (Exception, KeyboardInterrupt) as error:
            report["status"] = "failed"
            report["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            save_report(stream, report)
            print(f"Saved {report['status']} report: {output}", flush=True)
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
