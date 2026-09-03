from app.retrieval.search import search_chunks


TEST_CASES = [
    {
        "question": "What is the main contribution of the paper?",
        "expected_pages": [1, 7, 9],
    },
    {
        "question": "Which animal models are used in the study?",
        "expected_pages": [2],
    },
    {
        "question": "What was the purpose of the food restriction experiment?",
        "expected_pages": [6],
    },
    {
        "question": "How did cachexia affect glucose tolerance in C26 mice?",
        "expected_pages": [3, 6],
    },
    {
        "question": "When did increased glucose tolerance appear relative to weight loss?",
        "expected_pages": [3, 6, 9],
    },
    {
        "question": "How did KPC tumor-bearing mice differ from control mice in glucose tolerance?",
        "expected_pages": [6],
    },
    {
        "question": "How did three days of food restriction affect glucose tolerance?",
        "expected_pages": [6, 7],
    },
    {
        "question": "How did food restriction affect muscle insulin responsiveness?",
        "expected_pages": [7],
    },
    {
        "question": "What happened to AKT signaling in cachectic C26 mice?",
        "expected_pages": [7, 8],
    },
    {
        "question": "What are the three key findings highlighted in the discussion?",
        "expected_pages": [7],
    },
    {
        "question": "What limitation of the glucose tolerance experiments do the authors mention?",
        "expected_pages": [6],
    },
    {
        "question": "What do the authors conclude about insulin resistance in cancer cachexia?",
        "expected_pages": [9],
    },
]


def first_relevant_rank(retrieved_pages: list[int], expected_pages: list[int]) -> int | None:
    for rank, page in enumerate(retrieved_pages, start=1):
        if page in expected_pages:
            return rank

    return None


def main():
    recall_at_1 = 0
    recall_at_3 = 0
    recall_at_5 = 0
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
            recall_at_1 += 1

        if rank is not None and rank <= 3:
            recall_at_3 += 1

        if rank is not None and rank <= 5:
            recall_at_5 += 1

        print(f"\nQuestion: {test['question']}")
        print(f"Expected pages: {test['expected_pages']}")
        print(f"Retrieved pages: {retrieved_pages}")
        print(f"First relevant rank: {rank}")

    total = len(TEST_CASES)

    print("\n--- Results ---")
    print(f"Recall@1: {recall_at_1 / total:.2f}")
    print(f"Recall@3: {recall_at_3 / total:.2f}")
    print(f"Recall@5: {recall_at_5 / total:.2f}")
    print(f"MRR:      {reciprocal_rank_sum / total:.2f}")


if __name__ == "__main__":
    main()
    
