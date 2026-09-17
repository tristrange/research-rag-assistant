import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.rag import answer_question


class RagTests(unittest.TestCase):
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
