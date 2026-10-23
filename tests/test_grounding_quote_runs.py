import unittest

from app.grounding_evidence import _assemble_citation_context
from app.grounding_models import MAX_QUOTE_CHARS
from app.types import ChunkData, EvidenceQuote


class QuoteRunTests(unittest.TestCase):
    def join(self, text: str, quotes: list[str]) -> list[EvidenceQuote]:
        return _assemble_citation_context(
            [{"source_index": 0, "quote": q} for q in quotes],
            [ChunkData(document="test.pdf", page=1, chunk_index=0, text=text)],
        )

    def test_displays_the_entire_intervening_context_in_source_order(self) -> None:
        text = "We studied treated mice. In another experiment, we studied controls. Uptake rose."
        self.assertEqual(
            self.join(text, ["Uptake rose.", "We studied treated mice."]),
            [{"source_index": 0, "quote": text}],
        )

    def test_refuses_ambiguous_or_oversized_context(self) -> None:
        for text, quotes in [
            (
                "We studied treated mice. Uptake rose. We studied treated mice.",
                ["We studied treated mice.", "Uptake rose."],
            ),
            ("Scope. " + "x" * MAX_QUOTE_CHARS + " Result.", ["Scope.", "Result."]),
        ]:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                self.join(text, quotes)

    def test_groups_one_source_even_with_interleaved_citations(self) -> None:
        sources = [
            ChunkData(
                document=d, page=1, chunk_index=0, text="Treated mice. Uptake rose."
            )
            for d in ["a.pdf", "b.pdf"]
        ]
        citations: list[EvidenceQuote] = [
            {"source_index": 0, "quote": "Treated mice."},
            {"source_index": 1, "quote": "Uptake rose."},
            {"source_index": 0, "quote": "Uptake rose."},
        ]
        self.assertEqual(
            _assemble_citation_context(citations, sources),
            [{"source_index": 0, "quote": sources[0]["text"]}, citations[1]],
        )

    def test_overlaps_do_not_duplicate_or_invent_text(self) -> None:
        text = "Treated mice. Uptake rose."
        self.assertEqual(
            self.join(text, [text, "Uptake rose."]),
            [{"source_index": 0, "quote": text}],
        )
