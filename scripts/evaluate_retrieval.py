from app.retrieval.search import search_chunks


TEST_CASES = [
    {
        "question": "What is the main contribution of the paper?",
        "expected_pages": [1, 2],
    },
    {
        "question": "What dataset is used in the experiments?",
        "expected_pages": [4, 5],
    },
    {
        "question": "What limitations do the authors discuss?",
        "expected_pages": [8, 9],
    },
]


def main():
    correct = 0

    for test in TEST_CASES:
        results = search_chunks(test["question"], limit=5)
        retrieved_pages = [chunk.page for chunk in results]

        hit = any(
            page in test["expected_pages"]
            for page in retrieved_pages
        )

        if hit:
            correct += 1

        print(f"\nQuestion: {test['question']}")
        print(f"Expected pages: {test['expected_pages']}")
        print(f"Retrieved pages: {retrieved_pages}")
        print(f"Hit: {hit}")

    recall_at_5 = correct / len(TEST_CASES)

    print(f"\nRecall@5: {recall_at_5:.2f}")


if __name__ == "__main__":
    main()
