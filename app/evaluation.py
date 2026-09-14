"""Compare retrieval strategies without generating answers or changing the index."""

from collections.abc import Callable
from statistics import mean, median
from time import perf_counter
from typing import Literal, TypedDict

from app.db.models import Chunk
from app.types import ChunkData, RetrievalTestCase


class EvaluationCase(RetrievalTestCase):
    document: str


class RetrievalRun(TypedDict):
    sources: list[ChunkData]
    first_relevant_rank: int | None
    retrieval_ms: float
    reranking_ms: float
    total_ms: float
    candidate_first_relevant_rank: int | None


class QuestionResult(TypedDict):
    case: EvaluationCase
    baseline: list[RetrievalRun]
    reranked: list[RetrievalRun]
    change: Literal["improved", "worsened", "unchanged"]


class Metrics(TypedDict):
    hit_at_1: float
    hit_at_k: float
    mrr_at_k: float
    mean_total_ms: float
    median_total_ms: float
    mean_retrieval_ms: float
    mean_reranking_ms: float


class Comparison(TypedDict):
    top_k: int
    candidate_count: int
    repetitions: int
    baseline: Metrics
    reranked: Metrics
    candidate_hit_rate: float
    questions: list[QuestionResult]


Search = Callable[[str, int], list[Chunk]]
Rerank = Callable[[str, list[Chunk], int], list[Chunk]]


def relevant_rank(chunks: list[Chunk], case: EvaluationCase) -> int | None:
    return next((
        rank for rank, chunk in enumerate(chunks, 1)
        if chunk.document == case["document"] and chunk.page in case["expected_pages"]
    ), None)


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def measure(
    case: EvaluationCase,
    search: Search,
    rerank: Rerank | None,
    top_k: int,
    candidate_count: int,
) -> RetrievalRun:
    start = perf_counter()
    candidates = search(case["question"], candidate_count if rerank else top_k)
    retrieved = perf_counter()
    chunks = rerank(case["question"], candidates, top_k) if rerank else candidates
    finished = perf_counter() if rerank else retrieved
    # Enforce the reported cutoff even for an injected retrieval implementation.
    chunks = chunks[:top_k]
    return {
        "sources": [ChunkData(document=c.document, page=c.page,
                              chunk_index=c.chunk_index, text=c.text) for c in chunks],
        "first_relevant_rank": relevant_rank(chunks, case),
        "candidate_first_relevant_rank": relevant_rank(candidates, case),
        "retrieval_ms": (retrieved - start) * 1000,
        "reranking_ms": (finished - retrieved) * 1000,
        "total_ms": (finished - start) * 1000,
    }


def summarize(runs: list[RetrievalRun]) -> Metrics:
    return {
        "hit_at_1": mean(float(r["first_relevant_rank"] == 1) for r in runs),
        "hit_at_k": mean(float(r["first_relevant_rank"] is not None) for r in runs),
        "mrr_at_k": mean(reciprocal_rank(r["first_relevant_rank"]) for r in runs),
        "mean_total_ms": mean(r["total_ms"] for r in runs),
        "median_total_ms": median(r["total_ms"] for r in runs),
        "mean_retrieval_ms": mean(r["retrieval_ms"] for r in runs),
        "mean_reranking_ms": mean(r["reranking_ms"] for r in runs),
    }


def compare(
    cases: list[EvaluationCase],
    search: Search,
    rerank: Rerank,
    *,
    top_k: int = 3,
    candidate_count: int = 10,
    repetitions: int = 3,
) -> Comparison:
    if not cases:
        raise ValueError("At least one evaluation question is required")
    if not 1 <= top_k <= candidate_count or repetitions < 1:
        raise ValueError("Require 1 <= top_k <= candidate_count and repetitions >= 1")

    # Warm both paths before any samples: model loading, inference, and DB setup.
    measure(cases[0], search, None, top_k, candidate_count)
    measure(cases[0], search, rerank, top_k, candidate_count)
    questions: list[QuestionResult] = []
    for index, case in enumerate(cases):
        baseline: list[RetrievalRun] = []
        reranked: list[RetrievalRun] = []
        for repetition in range(repetitions):
            # Alternate ordering to avoid always giving one strategy the warm cache.
            order = [False, True] if (index + repetition) % 2 == 0 else [True, False]
            for use_reranker in order:
                run = measure(case, search, rerank if use_reranker else None,
                              top_k, candidate_count)
                (reranked if use_reranker else baseline).append(run)
        difference = summarize(reranked)["mrr_at_k"] - summarize(baseline)["mrr_at_k"]
        questions.append({
            "case": case, "baseline": baseline, "reranked": reranked,
            "change": "improved" if difference > 0 else "worsened" if difference < 0 else "unchanged",
        })

    baseline_runs = [r for q in questions for r in q["baseline"]]
    reranked_runs = [r for q in questions for r in q["reranked"]]
    return {
        "top_k": top_k, "candidate_count": candidate_count, "repetitions": repetitions,
        "baseline": summarize(baseline_runs), "reranked": summarize(reranked_runs),
        "candidate_hit_rate": mean(
            float(r["candidate_first_relevant_rank"] is not None) for r in reranked_runs
        ),
        "questions": questions,
    }
