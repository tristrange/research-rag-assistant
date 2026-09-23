import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.rag import answer_question
from app.retrieval.rerank import with_vector_reserve


class RagTests(unittest.TestCase):
    def test_verified_mode_uses_selected_sources_without_free_text_regeneration(self) -> None:
        source = Chunk(document="paper.pdf", page=10, chunk_index=1,
                       text="A cited study.", section="references")
        with patch("app.rag.search_chunks", return_value=[source]), \
                patch("app.rag.rerank_chunks", return_value=[source]), \
                patch("app.rag.grounded_answer", return_value="Checked answer") as grounded, \
                patch("app.rag.generate") as generate:
            result = answer_question("Question", answer_mode="verified")
        grounded.assert_called_once_with("Question", result["sources"])
        generate.assert_not_called()
        self.assertEqual(result["answer"], "Checked answer")

    def test_reference_sources_are_labelled_and_retained(self) -> None:
        reference = Chunk(document="paper.pdf", page=10, chunk_index=1,
                          text="A cited intervention study.", section="references")
        with patch("app.rag.search_chunks", return_value=[reference]), \
                patch("app.rag.rerank_chunks", return_value=[reference]), \
                patch("app.rag.generate", return_value="Cited work") as generate:
            result = answer_question("What does the cited study report?")
        self.assertEqual(result["sources"][0]["section"], "references")
        prompt = generate.call_args.args[0]
        self.assertIn("[paper.pdf, page 10, section references]", prompt)
        self.assertIn("A cited intervention study.", prompt)
        self.assertIn("require explicit evidence", prompt)

    def test_default_uses_reranking_and_passes_selected_context_to_generator(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=1, text="Evidence")
        rejected = Chunk(document="paper.pdf", page=3, chunk_index=1, text="Distractor")
        with patch("app.rag.search_chunks", return_value=[rejected, selected]) as search, \
                patch("app.rag.rerank_chunks", return_value=[selected]) as rerank, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question")
            search.assert_called_once_with("Question", limit=10)
            rerank.assert_called_once_with("Question", [rejected, selected], limit=3)
            prompt = generate.call_args.args[0]
            self.assertIn("Evidence", prompt)
            self.assertNotIn("Distractor", prompt)
            self.assertEqual(result["sources"][0]["page"], 2)

    def test_expanded_default_keeps_six_seeds_and_explicit_limit_is_respected(self) -> None:
        candidates = [Chunk(document="paper.pdf", page=1, chunk_index=i, text=f"Evidence {i}")
                      for i in range(10)]
        for requested, expected in [(None, 6), (3, 3)]:
            with self.subTest(limit=requested), \
                    patch("app.rag.search_chunks", return_value=candidates) as search, \
                    patch("app.rag.rerank_chunks", side_effect=lambda q, cs, limit: cs[:limit]) as rerank, \
                    patch("app.rag.expand_chunks", return_value=[]) as expand, \
                    patch("app.rag.generate", return_value="Answer"):
                answer_question("Question", limit=requested, expand_context=True)
            search.assert_called_once_with("Question", limit=10)
            rerank.assert_called_once_with("Question", candidates, limit=expected)
            expand.assert_called_once_with(candidates[:expected])

    def test_invalid_limit_fails_before_services(self) -> None:
        with patch("app.rag.search_chunks") as search:
            for limit in [0, -1]:
                with self.assertRaises(ValueError):
                    answer_question("Question", limit=limit)
            search.assert_not_called()

    def test_vector_reserve_adds_first_unselected_vector_candidate_to_verified_sources(self) -> None:
        candidates = [
            Chunk(document="paper.pdf", page=1, chunk_index=i, text=f"Evidence {i}")
            for i in range(5)
        ]
        reranked = [candidates[2], candidates[0], candidates[4]]
        with patch("app.rag.search_chunks", return_value=candidates) as search, \
                patch("app.rag.rerank_chunks", return_value=reranked) as rerank, \
                patch("app.rag.grounded_answer", return_value="Checked") as grounded:
            result = answer_question("Question", answer_mode="verified", reserve_vector_candidate=True)

        search.assert_called_once_with("Question", limit=10)
        rerank.assert_called_once_with("Question", candidates, limit=3)
        self.assertEqual([source["chunk_index"] for source in result["sources"]], [2, 0, 4, 1])
        grounded.assert_called_once_with("Question", result["sources"])

    def test_vector_reserve_rejects_incompatible_modes_before_search(self) -> None:
        with patch("app.rag.search_chunks") as search:
            with self.assertRaisesRegex(ValueError, "unexpanded reranking"):
                answer_question("Question", reserve_vector_candidate=True, use_reranking=False)
            with self.assertRaisesRegex(ValueError, "unexpanded reranking"):
                answer_question("Question", reserve_vector_candidate=True, expand_context=True)
            with self.assertRaisesRegex(ValueError, "limit below 10"):
                answer_question("Question", limit=10, reserve_vector_candidate=True)
            search.assert_not_called()

    def test_vector_reserve_fails_when_corpus_has_no_extra_candidate(self) -> None:
        only_chunk = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence")
        with self.assertRaisesRegex(ValueError, "unselected vector candidate"):
            with_vector_reserve([only_chunk], [only_chunk])

    def test_vector_mode_uses_same_generation_path_without_reranking(self) -> None:
        with patch("app.rag.search_chunks", return_value=[]) as search, \
                patch("app.rag.rerank_chunks") as rerank, \
                patch("app.rag.expand_chunks") as expand, \
                patch("app.rag.generate", return_value="Not enough information") as generate:
            result = answer_question("Question", use_reranking=False)
            search.assert_called_once_with("Question", limit=3)
            rerank.assert_not_called()
            expand.assert_not_called()
            generate.assert_called_once()
            self.assertEqual(result["answer"], "Not enough information")

    def test_expanded_sources_are_the_exact_evidence_sent_to_generator(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=1, text="Seed")
        expanded = [{
            "document": "paper.pdf",
            "page": 2,
            "chunk_index": 0,
            "text": "Previous. Seed. Following.",
        }]
        with patch("app.rag.search_chunks", return_value=[selected]), \
                patch("app.rag.rerank_chunks", return_value=[selected]), \
                patch("app.rag.expand_chunks", return_value=expanded) as expand, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question", expand_context=True)

        expand.assert_called_once_with([selected])
        prompt = generate.call_args.args[0]
        self.assertIn("[paper.pdf, page 2, section unknown]\nPrevious. Seed. Following.", prompt)
        self.assertEqual(result["sources"], expanded)

    def test_unexpanded_path_preserves_ranked_chunks_and_does_not_lookup_neighbors(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=7, text="Evidence")
        with patch("app.rag.search_chunks", return_value=[selected]), \
                patch("app.rag.rerank_chunks", return_value=[selected]), \
                patch("app.rag.expand_chunks") as expand, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question")

        expand.assert_not_called()
        self.assertIn("[paper.pdf, page 2, section unknown]\nEvidence", generate.call_args.args[0])
        self.assertEqual(result["sources"], [{
            "document": "paper.pdf",
            "page": 2,
            "chunk_index": 7,
            "text": "Evidence",
            "section": "unknown",
        }])


if __name__ == "__main__":
    unittest.main()
