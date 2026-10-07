"""Compare bounded expanded contexts without generating or judging answers."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import cast

from app.answer_evaluation import AnswerEvaluationCase, evidence_found
from app.db.models import Chunk
from app.embeddings import EMBEDDING_MODEL
from app.ingestion.pdf import extract_pages
from app.retrieval import CANDIDATE_COUNT, DEFAULT_TOP_K, EXPANDED_TOP_K
from app.retrieval.context import MAX_CONTEXT_CHARS, NEIGHBOR_RADIUS, expand_chunks, render_context
from app.retrieval.rerank import MODEL_NAME, rerank_chunks
from app.retrieval.search import search_chunks
from app.types import ChunkData
from scripts.answer_quality_cases import ANSWER_CASES, PAPER_SHA256
from scripts.compare_reranking import snapshot
from scripts.evaluate_answers import (
    cases_hash, indexed_sources, load_benchmark, reserve_output, save_report,
    validate_index, validate_labels,
)


def sources_for(chunks: list[Chunk]) -> list[ChunkData]:
    return [ChunkData(document=c.document, page=c.page, chunk_index=c.chunk_index,
                      text=c.text, section=c.section or "unknown") for c in chunks]


def coverage(case: AnswerEvaluationCase, sources: list[ChunkData]) -> list[bool]:
    return [evidence_found(label, sources) for label in case["evidence"]]


def compare_case(
    case: AnswerEvaluationCase, cutoffs: list[int], *,
    document: str, candidate_count: int = CANDIDATE_COUNT,
) -> dict[str, object]:
    start = perf_counter()
    candidates = search_chunks(case["question"], candidate_count, document=document)
    searched = perf_counter()
    ranked = rerank_chunks(case["question"], candidates, candidate_count)
    reranked = perf_counter()
    variants: dict[str, object] = {}
    for cutoff in cutoffs:
        expanding = perf_counter()
        sources = expand_chunks(ranked[:cutoff])
        elapsed_ms = (perf_counter() - expanding) * 1000
        variants[str(cutoff)] = {
            "seed_hits": coverage(case, sources_for(ranked[:cutoff])),
            "expanded_hits": coverage(case, sources), "sources": sources,
            "context_chars": len(render_context(sources)), "expansion_ms": elapsed_ms,
            "retrieval_total_ms": (reranked - start) * 1000 + elapsed_ms,
        }
    return {
        "case": case, "candidate_sources": sources_for(candidates),
        "candidate_hits": coverage(case, sources_for(candidates)),
        "reranked_sources": sources_for(ranked), "variants": variants,
        "search_ms": (searched - start) * 1000,
        "rerank_ms": (reranked - searched) * 1000,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--pdf", type=Path, default=Path("data/sample.pdf"))
    parser.add_argument("--case", dest="case_ids", action="append",
                        help="select an answerable benchmark case; repeat to select more")
    parser.add_argument("--candidates", type=int, choices=range(1, 101), default=CANDIDATE_COUNT,
                        metavar="1..100", help="vector candidate pool to inspect (default: 10)")
    parser.add_argument("--baseline-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--top-k", type=int, default=EXPANDED_TOP_K)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.baseline_k < args.top_k <= args.candidates or args.repetitions < 1:
        parser.error("cutoffs require 1 <= baseline-k < top-k <= candidates and repetitions >= 1")
    cases = ANSWER_CASES
    paper_hash = PAPER_SHA256
    document = "sample.pdf"
    if args.benchmark:
        manifest = load_benchmark(args.benchmark)
        cases = [cast(AnswerEvaluationCase, c.model_dump()) for c in manifest.cases]
        paper_hash = manifest.metadata.paper_sha256
        document = manifest.metadata.document
    if args.case_ids is not None:
        if len(args.case_ids) != len(set(args.case_ids)):
            parser.error("Case selections must not contain duplicates")
        unknown = set(args.case_ids) - {case["id"] for case in cases}
        if unknown:
            parser.error("Unknown case IDs: " + ", ".join(sorted(unknown)))
        selected = set(args.case_ids)
        cases = [case for case in cases if case["id"] in selected]
        if any(not case["answerable"] for case in cases):
            parser.error("Selected cases must be answerable; coverage does not measure refusals")
    if args.pdf.name != document or sha256(args.pdf.read_bytes()).hexdigest() != paper_hash:
        parser.error("PDF must match the benchmark filename and fingerprint")
    if args.output.exists():
        parser.error("Output exists; choose a new path")
    cases = [case for case in cases if case["answerable"]]
    if not cases:
        parser.error("Coverage comparison requires at least one answerable case")
    pages = extract_pages(str(args.pdf))
    validate_labels(cases, pages)
    before = snapshot(document)
    # Both retrieval and PDF-text validation use the benchmark's exact filename.
    # The full-library snapshot still detects changes anywhere during the run.
    selected_sources = [source for source in indexed_sources() if source["document"] == document]
    if not selected_sources:
        parser.error("The evaluation paper has no indexed text")
    validate_index(selected_sources, pages)
    results: list[dict[str, object]] = []
    report: dict[str, object] = {
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "document": document, "requested_case_ids": [case["id"] for case in cases],
        "corpus": before, "paper_sha256": paper_hash, "cases_sha256": cases_hash(cases),
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "embedding_model": EMBEDDING_MODEL, "reranker_model": MODEL_NAME,
        "baseline_k": args.baseline_k, "top_k": args.top_k,
        "candidates": args.candidates, "repetitions": args.repetitions,
        "neighbor_radius": NEIGHBOR_RADIUS, "max_context_chars": MAX_CONTEXT_CHARS,
        "methodology": "Inspected development labels, not a held-out quality estimate. "
        "One warmup on the first case; no generation or judge calls. "
        "Cutoffs share one candidate search and reranking per case/repetition; "
        "Retrieval is filtered to the benchmark document within the existing library; "
        "the corpus fingerprint covers the full library. "
        "expansion is measured separately, baseline first. Latency excludes generation. "
        "Exact normalized quotes must fit in a single returned source. "
        "Label matches do not establish unlabelled qualifiers or answer completeness. "
        "Unanswerable cases are excluded; this does not measure refusal quality.",
        "results": results,
    }
    reserve_output(args.output)
    save_report(args.output, report)
    try:
        cutoffs = [args.baseline_k, args.top_k]
        compare_case(cases[0], cutoffs, document=document, candidate_count=args.candidates)
        for repetition in range(args.repetitions):
            for case in cases:
                result = compare_case(case, cutoffs, document=document, candidate_count=args.candidates)
                result["repetition"] = repetition + 1
                results.append(result)
                save_report(args.output, report)
                print(f"Completed repetition {repetition + 1}: {case['id']}", flush=True)
        if snapshot(document) != before:
            raise RuntimeError("Corpus changed during comparison; discard these results")
        report["status"] = "complete"
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
