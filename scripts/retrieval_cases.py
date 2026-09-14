"""Shared development questions for data/sample.pdf (not a held-out test set)."""

from app.types import RetrievalTestCase


TEST_CASES: list[RetrievalTestCase] = [
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
