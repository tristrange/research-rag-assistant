import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.retrieval.rerank import rerank_chunks


class RerankTests(unittest.TestCase):
    def test_empty_candidates_do_not_load_model(self) -> None:
        with patch("app.retrieval.rerank.get_model") as get_model:
            self.assertEqual(rerank_chunks("question", []), [])
            get_model.assert_not_called()

    def test_descending_scores_cutoff_and_input_preserved(self) -> None:
        chunks = [Chunk(text=text) for text in ["first", "second", "third"]]
        with patch("app.retrieval.rerank.get_model") as get_model:
            get_model.return_value.predict.return_value = [0.1, 0.9, 0.5]
            self.assertEqual(rerank_chunks("question", chunks, 2), [chunks[1], chunks[2]])
            get_model.return_value.predict.assert_called_once_with([
                ("question", "first"), ("question", "second"), ("question", "third"),
            ])
        self.assertEqual([c.text for c in chunks], ["first", "second", "third"])


if __name__ == "__main__":
    unittest.main()
