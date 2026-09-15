import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.rag import answer_question


class RagTests(unittest.TestCase):
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
                patch("app.rag.generate", return_value="Not enough information") as generate:
            result = answer_question("Question", use_reranking=False)
            search.assert_called_once_with("Question", limit=3)
            rerank.assert_not_called()
            generate.assert_called_once()
            self.assertEqual(result["answer"], "Not enough information")


if __name__ == "__main__":
    unittest.main()
