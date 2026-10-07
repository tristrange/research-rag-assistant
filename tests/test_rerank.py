import unittest
from unittest.mock import patch

from app.db.models import Chunk
from app.retrieval.rerank import rerank_chunks, rerank_with_page_reserve


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

    def test_vector_slot_keeps_next_vector_candidate_and_top_reranked_candidate(self) -> None:
        # Six result passages outrank the cohort passage, while the timing
        # passage lies outside the old ten-candidate pool and has the best score.
        chunks = [
            Chunk(document="paper.pdf", page=1, chunk_index=index,
                  text=("Duplicate result passage" if index in (0, 1, 2, 3, 5, 6)
                        else f"Passage {index}"))
            for index in range(20)
        ]
        scores = [0.99, 0.98, 0.97, 0.96, 0.10, 0.95, 0.94] + [0.0] * 6 + [1.0] + [0.0] * 6
        original = list(chunks)

        with patch("app.retrieval.rerank.get_model") as get_model:
            get_model.return_value.predict.return_value = scores
            selected = rerank_with_page_reserve("Question", chunks, limit=6)

        self.assertEqual([chunk.chunk_index for chunk in selected], [13, 0, 1, 2, 3, 4])
        self.assertEqual(len(selected), 6)
        self.assertEqual(len({(chunk.document, chunk.page, chunk.chunk_index) for chunk in selected}), 6)
        self.assertEqual(chunks, original)
        get_model.return_value.predict.assert_called_once_with([
            ("Question", chunk.text) for chunk in chunks
        ])

    def test_vector_slot_falls_back_for_single_slot_or_small_candidate_pool(self) -> None:
        chunks = [Chunk(document="paper.pdf", page=1, chunk_index=index, text=f"Passage {index}")
                  for index in range(2)]
        with patch("app.retrieval.rerank.get_model") as get_model:
            get_model.return_value.predict.return_value = [0.2, 0.9]
            one = rerank_with_page_reserve("Question", chunks, limit=1)
            self.assertEqual([chunk.chunk_index for chunk in one], [1])

        with patch("app.retrieval.rerank.get_model") as get_model:
            get_model.return_value.predict.return_value = [0.2, 0.9]
            small = rerank_with_page_reserve("Question", chunks, limit=6)
            self.assertEqual([chunk.chunk_index for chunk in small], [1, 0])
        self.assertEqual(len({(chunk.document, chunk.page, chunk.chunk_index) for chunk in small}), 2)

    def test_vector_reserve_prefers_a_new_page_over_repeated_numerical_passages(self) -> None:
        chunks = [Chunk(document="paper.pdf", page=6 if index == 3 else 7,
                        chunk_index=index, text=f"Passage {index}") for index in range(10)]
        scores = [0.9995, 0.9816, 0.9853, 0.9689, 0.9754, 0.9992, 0.9920, 0.01, 0.1, 0.9883]
        with patch("app.retrieval.rerank.get_model") as get_model:
            get_model.return_value.predict.return_value = scores
            selected = rerank_with_page_reserve("Food restriction comparison?", chunks, limit=6)
        self.assertEqual([chunk.chunk_index for chunk in selected], [0, 5, 6, 9, 2, 3])
        self.assertEqual(selected[-1].page, 6)


if __name__ == "__main__":
    unittest.main()
