import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.evaluation import EvaluationCase, compare, measure, relevant_rank


def chunk(page: int, document: str = "sample.pdf") -> Chunk:
    return Chunk(document=document, page=page, chunk_index=0, text=f"Page {page}")


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = EvaluationCase(question="Question", document="sample.pdf", expected_pages=[7, 9])

    def test_relevance_requires_both_document_and_page(self) -> None:
        self.assertEqual(relevant_rank([chunk(7, "other.pdf"), chunk(7)], self.case), 2)
        self.assertIsNone(relevant_rank([chunk(7, "other.pdf")], self.case))

    def test_improvement_cutoff_and_candidate_diagnostic(self) -> None:
        calls: list[int] = []

        def search(query: str, limit: int) -> list[Chunk]:
            calls.append(limit)
            return [chunk(1), chunk(2), chunk(3), chunk(7)][:limit]

        def rerank(query: str, chunks: list[Chunk], limit: int) -> list[Chunk]:
            return list(reversed(chunks))[:limit]

        result = compare([self.case], search, rerank, candidate_count=4, repetitions=2)
        self.assertEqual(result["baseline"]["hit_at_k"], 0)
        self.assertEqual(result["baseline"]["mrr_at_k"], 0)
        self.assertEqual(result["reranked"]["hit_at_1"], 1)
        self.assertEqual(result["reranked"]["mrr_at_k"], 1)
        self.assertEqual(result["candidate_hit_rate"], 1)
        self.assertEqual(result["questions"][0]["change"], "improved")
        self.assertEqual(len(result["questions"][0]["baseline"]), 2)
        # Two warmups, then alternating measured order; baseline retrieves only k.
        self.assertEqual(calls, [3, 4, 3, 4, 4, 3])

    def test_worsening_and_mrr_are_not_recall(self) -> None:
        def search(query: str, limit: int) -> list[Chunk]:
            return [chunk(7), chunk(2)][:limit]

        def rerank(query: str, chunks: list[Chunk], limit: int) -> list[Chunk]:
            return list(reversed(chunks))[:limit]

        result = compare([self.case], search, rerank, repetitions=1)
        self.assertEqual(result["reranked"]["hit_at_k"], 1)
        self.assertEqual(result["reranked"]["mrr_at_k"], 0.5)
        self.assertEqual(result["questions"][0]["change"], "worsened")

    def test_empty_retrieval_counts_as_miss(self) -> None:
        result = compare([self.case], lambda query, limit: [],
                         lambda query, chunks, limit: [], repetitions=1)
        self.assertEqual(result["candidate_hit_rate"], 0)
        self.assertEqual(result["reranked"]["mrr_at_k"], 0)
        self.assertEqual(result["questions"][0]["change"], "unchanged")

    def test_latency_separates_retrieval_and_reranking(self) -> None:
        with patch("app.evaluation.perf_counter", side_effect=[1.0, 1.1, 1.4]):
            run = measure(self.case, lambda query, limit: [chunk(7)],
                          lambda query, chunks, limit: chunks, 3, 10)
        self.assertAlmostEqual(run["retrieval_ms"], 100)
        self.assertAlmostEqual(run["reranking_ms"], 300)
        self.assertAlmostEqual(run["total_ms"], 400)

    def test_invalid_configuration_does_not_call_services(self) -> None:
        def search(query: str, limit: int) -> list[Chunk]:
            self.fail("Invalid configuration must not call retrieval")

        for cases, k, candidates, repeats in [([], 3, 10, 1), ([self.case], 0, 10, 1),
                                             ([self.case], 4, 3, 1), ([self.case], 3, 10, 0)]:
            with self.subTest(k=k, candidates=candidates, repeats=repeats):
                with self.assertRaises(ValueError):
                    compare(cases, search, lambda query, chunks, limit: chunks,
                            top_k=k, candidate_count=candidates, repetitions=repeats)


if __name__ == "__main__":
    unittest.main()
