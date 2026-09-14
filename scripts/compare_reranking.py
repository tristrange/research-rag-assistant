"""Run with: uv run python -m scripts.compare_reranking --help."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
from typing import TypedDict

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import EMBEDDING_MODEL
from app.evaluation import Comparison, EvaluationCase, compare
from app.retrieval.search import search_chunks
from scripts.retrieval_cases import TEST_CASES


class CorpusSnapshot(TypedDict):
    sha256: str
    chunks_by_document: dict[str, int]


def snapshot(document: str) -> CorpusSnapshot:
    """Fingerprint stored text and vectors, and reject a misleading duplicate index."""
    with SessionLocal() as db:
        chunks = list(db.scalars(select(Chunk).order_by(Chunk.id)))
        if not any(c.document == document for c in chunks):
            raise ValueError(f"No indexed chunks for {document!r}; index the evaluation paper first")
        identities = [(c.document, c.page, c.chunk_index) for c in chunks]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate document/page/chunk entries found; reindex before comparing")
        digest = sha256()
        for c in chunks:
            digest.update(json.dumps([
                c.id, c.document, c.page, c.chunk_index, c.text,
                [float(value) for value in c.embedding],
            ], ensure_ascii=False).encode())
        return {"sha256": digest.hexdigest(),
                "chunks_by_document": dict(Counter(c.document for c in chunks))}


def print_comparison(result: Comparison) -> None:
    k = result["top_k"]
    print(f"{'Strategy':<12} {'Hit@1':>8} {f'Hit@{k}':>8} {f'MRR@{k}':>8} {'Mean ms':>10} {'Median ms':>10}")
    for label, metrics in [("Vector", result["baseline"]), ("Reranked", result["reranked"])]:
        print(f"{label:<12} {metrics['hit_at_1']:>8.3f} {metrics['hit_at_k']:>8.3f} "
              f"{metrics['mrr_at_k']:>8.3f} {metrics['mean_total_ms']:>10.1f} "
              f"{metrics['median_total_ms']:>10.1f}")
    print(f"Candidate Hit@{result['candidate_count']}: {result['candidate_hit_rate']:.3f}")
    print("\nQuestion changes use mean reciprocal rank; passages below are from the first repetition.")
    for question in result["questions"]:
        case = question["case"]
        print(f"\n[{question['change']}] {case['question']}")
        print(f"Expected: {case['document']} pages {case['expected_pages']}")
        for label, runs in [("Vector", question["baseline"]), ("Reranked", question["reranked"])]:
            print(f"  {label}: first relevant ranks {[r['first_relevant_rank'] for r in runs]}")
            for source in runs[0]["sources"]:
                excerpt = " ".join(source["text"].split())[:240]
                print(f"    {source['document']} p.{source['page']} chunk {source['chunk_index']}: {excerpt}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare vector retrieval against reranking on the shared development questions.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--document", default="sample.pdf", help="Indexed filename of the paper the shared questions describe")
    parser.add_argument("--output", type=Path, help="JSON report path; defaults to a timestamped file in evaluation-results/")
    args = parser.parse_args()
    if not 1 <= args.top_k <= args.candidates or args.repetitions < 1:
        parser.error("require 1 <= --top-k <= --candidates and --repetitions >= 1")

    # --help and validation do not load the model or connect to local services.
    before = snapshot(args.document)
    from app.retrieval.rerank import MODEL_NAME, rerank_chunks

    cases: list[EvaluationCase] = [EvaluationCase(document=args.document, **case) for case in TEST_CASES]
    print(f"Warming both strategies, then running {len(cases)} questions x {args.repetitions} repetitions...", flush=True)
    result = compare(cases, search_chunks, rerank_chunks, top_k=args.top_k,
                     candidate_count=args.candidates, repetitions=args.repetitions)
    if snapshot(args.document) != before:
        raise RuntimeError("The index changed during evaluation; discard this run and retry with a stable index")

    now = datetime.now(timezone.utc)
    report = {
        "schema_version": 1,
        "created_at": now.isoformat(),
        "corpus": before,
        "embedding_model": EMBEDDING_MODEL,
        "reranker_model": MODEL_NAME,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "sentence_transformers": version("sentence-transformers"),
                        "torch": version("torch")},
        "methodology": "Page-level development labels matched by document and page. Each path is warmed once. "
                       "Order alternates per question/repetition. Timings include query embedding and database retrieval; "
                       "reranked timings also include cross-encoder inference. No answer generation. "
                       "Mean/median latency and quality metrics aggregate all measured repetitions.",
        "comparison": result,
    }
    output = args.output or Path("evaluation-results") / f"reranking-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never silently overwrite a previous experiment.
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print_comparison(result)
    print(f"\nSaved report: {output}")


if __name__ == "__main__":
    main()
