import unittest
from unittest.mock import MagicMock, patch

from app.db.models import Chunk
from app.retrieval.context import (
    MAX_CONTEXT_CHARS,
    _merge_adjacent_text,
    expand_chunks,
    render_context,
)
from app.types import ChunkData


def chunk(
    index: int,
    text: str,
    *,
    document: str = "paper.pdf",
    page: int = 4,
) -> Chunk:
    return Chunk(document=document, page=page, chunk_index=index, text=text)


class ContextExpansionTests(unittest.TestCase):
    def _expand_with_rows(
        self,
        seeds: list[Chunk],
        rows: list[Chunk],
        *,
        max_chars: int = MAX_CONTEXT_CHARS,
    ) -> tuple[list[ChunkData], MagicMock]:
        db = MagicMock()
        db.scalars.return_value = rows
        with patch("app.retrieval.context.SessionLocal", return_value=db) as session:
            sources = expand_chunks(seeds, max_chars=max_chars)
        session.assert_called_once_with()
        db.scalars.assert_called_once()
        db.close.assert_called_once_with()
        return sources, db

    def test_empty_seeds_need_no_database_lookup(self) -> None:
        with patch("app.retrieval.context.SessionLocal") as session:
            self.assertEqual(expand_chunks([]), [])
        session.assert_not_called()

    def test_expands_two_neighbors_each_way_and_removes_exact_boundary_overlap(self) -> None:
        seed = chunk(2, "Shared sentence. Beta result.")
        second_previous = chunk(0, "Opening. Alpha finding.")
        previous = chunk(1, "Alpha finding. Shared sentence.")
        following = chunk(3, "Beta result. Gamma finding.")
        second_following = chunk(4, "Gamma finding. Delta.")

        sources, _ = self._expand_with_rows(
            [seed], [second_following, following, second_previous, previous],
        )

        self.assertEqual(sources, [{
            "document": "paper.pdf",
            "page": 4,
            "chunk_index": 0,
            "text": (
                "Opening. Alpha finding. Shared sentence. "
                "Beta result. Gamma finding. Delta."
            ),
        }])

    def test_lookup_and_merge_stay_within_the_seed_document_and_page(self) -> None:
        seed = chunk(2, "Seed.")
        valid = chunk(1, "Previous. ")
        wrong_page = chunk(3, "Wrong page.", page=5)
        wrong_document = chunk(3, "Wrong document.", document="other.pdf")

        sources, db = self._expand_with_rows(
            [seed], [wrong_page, wrong_document, valid],
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["page"], 4)
        self.assertEqual(sources[0]["document"], "paper.pdf")
        self.assertEqual(sources[0]["text"], "Previous. Seed.")
        params = db.scalars.call_args.args[0].compile().params
        self.assertIn("paper.pdf", params.values())
        self.assertIn(4, params.values())
        self.assertNotIn("other.pdf", params.values())
        self.assertNotIn(5, params.values())

    def test_first_chunk_queries_only_the_nonnegative_page_neighbor(self) -> None:
        seed = chunk(0, "First. ")
        following = chunk(1, "Second.")

        sources, db = self._expand_with_rows([seed], [following])

        self.assertEqual(sources[0]["chunk_index"], 0)
        self.assertEqual(sources[0]["text"], "First. Second.")
        params = db.scalars.call_args.args[0].compile().params
        integer_values = [value for value in params.values() if isinstance(value, int)]
        self.assertNotIn(-1, integer_values)

    def test_overlapping_ranked_seed_windows_are_deduplicated(self) -> None:
        higher_ranked = chunk(2, "two ")
        lower_ranked = chunk(3, "three ")
        previous = chunk(1, "one ")
        following = chunk(4, "four")

        sources, _ = self._expand_with_rows(
            [higher_ranked, lower_ranked], [previous, following],
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["chunk_index"], 1)
        self.assertEqual(sources[0]["text"], "one two three four")

    def test_budget_keeps_all_ranked_seeds_before_spending_on_neighbors(self) -> None:
        first = chunk(5, "First seed.", document="a.pdf", page=1)
        second = chunk(8, "Second seed.", document="b.pdf", page=2)
        neighbor = chunk(4, "A neighbor that cannot fit. ", document="a.pdf", page=1)
        seed_sources = [
            ChunkData(document="a.pdf", page=1, chunk_index=5, text="First seed."),
            ChunkData(document="b.pdf", page=2, chunk_index=8, text="Second seed."),
        ]
        budget = len(render_context(seed_sources))

        sources, _ = self._expand_with_rows(
            [first, second], [neighbor], max_chars=budget,
        )

        self.assertEqual(sources, seed_sources)
        self.assertLessEqual(len(render_context(sources)), budget)

    def test_budget_drops_lower_priority_window_whole(self) -> None:
        first = chunk(5, "First seed.", document="a.pdf", page=1)
        second = chunk(8, "Second seed.", document="b.pdf", page=2)
        first_source = ChunkData(
            document="a.pdf", page=1, chunk_index=5, text="First seed.",
        )
        budget = len(render_context([first_source]))

        sources, _ = self._expand_with_rows(
            [first, second], [], max_chars=budget,
        )

        self.assertEqual(sources, [first_source])
        self.assertEqual(len(render_context(sources)), budget)

    def test_overlap_merge_does_not_remove_internal_or_one_character_matches(self) -> None:
        self.assertEqual(
            _merge_adjacent_text("Shared phrase, then tail.", "Shared phrase, then next."),
            "Shared phrase, then tail. Shared phrase, then next.",
        )
        self.assertEqual(_merge_adjacent_text("Alpha.", ".Beta"), "Alpha. .Beta")

    def test_nonoverlapping_chunks_do_not_fuse_words(self) -> None:
        self.assertEqual(_merge_adjacent_text("red", "mice"), "red mice")
        self.assertEqual(
            _merge_adjacent_text("First fact.", "Next fact."),
            "First fact. Next fact.",
        )

    def test_rendered_default_budget_includes_headers_and_separators(self) -> None:
        seed = chunk(0, "x" * MAX_CONTEXT_CHARS)

        sources, _ = self._expand_with_rows([seed], [])

        self.assertEqual(sources, [])
        self.assertLessEqual(len(render_context(sources)), MAX_CONTEXT_CHARS)


if __name__ == "__main__":
    unittest.main()
