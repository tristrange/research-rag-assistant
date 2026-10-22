import unittest

from app.grounding_evidence import _join_adjacent_citations
from app.grounding_models import MAX_QUOTE_CHARS
from app.types import ChunkData, EvidenceQuote


class QuoteRunTests(unittest.TestCase):
    def join(self, text: str, quotes: list[str]) -> list[EvidenceQuote]:
        return _join_adjacent_citations(
            [{"source_index": 0, "quote": q} for q in quotes],
            [ChunkData(document="test.pdf", page=1, chunk_index=0, text=text)],
        )

    def test_joins_only_selected_contiguous_text_in_original_order(self) -> None:
        result = self.join(
            "We studied treated mice.\n\nUptake rose. Recovery was partial.",
            ["Uptake rose.", "We studied treated mice.", "Recovery was partial."],
        )
        self.assertEqual(
            result,
            [
                {
                    "source_index": 0,
                    "quote": "We studied treated mice. Uptake rose. Recovery was partial.",
                }
            ],
        )

    def test_keeps_hidden_experiment_boundary_and_repeated_wording_separate(
        self,
    ) -> None:
        for text in [
            "We studied treated mice. In a separate experiment, controls were tested. Uptake rose.",
            "We studied treated mice. Uptake rose. We studied treated mice.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(
                    len(self.join(text, ["We studied treated mice.", "Uptake rose."])),
                    2,
                )

    def test_never_joins_different_sources_or_unselected_overlapping_text(self) -> None:
        sources = [
            ChunkData(
                document=d, page=1, chunk_index=0, text="Treated mice. Uptake rose."
            )
            for d in ["a.pdf", "b.pdf"]
        ]
        citations: list[EvidenceQuote] = [
            {"source_index": 0, "quote": "Treated mice."},
            {"source_index": 1, "quote": "Uptake rose."},
        ]
        self.assertEqual(_join_adjacent_citations(citations, sources), citations)
        overlapping = ["Treated mice. Uptake rose.", "Uptake rose."]
        self.assertEqual(len(self.join(sources[0]["text"], overlapping)), 2)

    def test_preserves_quote_limit(self) -> None:
        first = "x" * (MAX_QUOTE_CHARS - 1) + "."
        self.assertEqual(len(self.join(first + " Next.", [first, "Next."])), 2)
