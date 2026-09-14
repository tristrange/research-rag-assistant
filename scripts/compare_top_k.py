from app.retrieval.search import search_chunks
from scripts.retrieval_cases import TEST_CASES


TOP_K_VALUES = [1, 3, 5, 8]


def first_relevant_rank(
    retrieved_pages: list[int],
    expected_pages: list[int],
) -> int | None:
    for rank, page in enumerate(retrieved_pages, start=1):
        if page in expected_pages:
            return rank

    return None


def evaluate(top_k: int) -> dict[str, float]:
    hits = 0
    reciprocal_rank_sum = 0.0

    for test in TEST_CASES:
        results = search_chunks(
            test["question"],
            limit=top_k,
        )

        retrieved_pages = [chunk.page for chunk in results]

        rank = first_relevant_rank(
            retrieved_pages,
            test["expected_pages"],
        )

        if rank is not None:
            hits += 1
            reciprocal_rank_sum += 1 / rank

    total = len(TEST_CASES)

    return {
        "hit": hits / total,
        "mrr": reciprocal_rank_sum / total,
    }


def main() -> None:
    print(
        f"{'Top-k':>8} "
        f"{'Hit@k':>10} "
        f"{'MRR':>8}"
    )

    for top_k in TOP_K_VALUES:
        metrics = evaluate(top_k)

        print(
            f"{top_k:>8} "
            f"{metrics['hit']:>10.2f} "
            f"{metrics['mrr']:>8.2f}"
        )


if __name__ == "__main__":
    main()
