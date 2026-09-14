from app.retrieval.search import search_chunks
from scripts.retrieval_cases import TEST_CASES


def first_relevant_rank(retrieved_pages: list[int], expected_pages: list[int]) -> int | None:
    for rank, page in enumerate(retrieved_pages, start=1):
        if page in expected_pages:
            return rank

    return None


def main() -> None:
    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_rank_sum = 0.0

    for test in TEST_CASES:
        results = search_chunks(test["question"], limit=5)
        retrieved_pages = [chunk.page for chunk in results]

        rank = first_relevant_rank(
            retrieved_pages,
            test["expected_pages"],
        )

        if rank is not None:
            reciprocal_rank_sum += 1 / rank

        if rank is not None and rank <= 1:
            hit_at_1 += 1

        if rank is not None and rank <= 3:
            hit_at_3 += 1

        if rank is not None and rank <= 5:
            hit_at_5 += 1

        print(f"\nQuestion: {test['question']}")
        print(f"Expected pages: {test['expected_pages']}")
        print(f"Retrieved pages: {retrieved_pages}")
        print(f"First relevant rank: {rank}")

    total = len(TEST_CASES)

    print("\n--- Results ---")
    print(f"Hit@1: {hit_at_1 / total:.2f}")
    print(f"Hit@3: {hit_at_3 / total:.2f}")
    print(f"Hit@5: {hit_at_5 / total:.2f}")
    print(f"MRR:      {reciprocal_rank_sum / total:.2f}")


if __name__ == "__main__":
    main()
    
