import unittest

from app.ingestion.chunking import chunk_pages
from app.ingestion.sections import heading_section
from app.types import PageData


def page(
    text: str,
    document: str = "paper.pdf",
    number: int = 1,
    section: str | None = None,
) -> PageData:
    result = PageData(document=document, page=number, text=text)
    if section is not None:
        result["section"] = section
    return result


class SectionRecognitionTests(unittest.TestCase):
    def test_recognizes_numbered_primary_headings_conservatively(self) -> None:
        self.assertEqual(heading_section("1. INTRODUCTION"), "introduction")
        self.assertEqual(heading_section("2.1 Materials and Methods"), "methods")
        self.assertEqual(heading_section("3 RESULTS:"), "results")
        self.assertEqual(heading_section("Background"), "background")
        self.assertIsNone(heading_section("Results from the first experiment"))
        self.assertIsNone(heading_section("The discussion continues"))

    def test_splits_same_page_sections_and_preserves_exact_text(self) -> None:
        text = (
            "ABSTRACT\nSummary.\n"
            "1. INTRODUCTION\nPrior work.\n"
            "3. RESULTS\nOur observation.\n"
            "REFERENCES\n[1] Prior citation."
        )

        chunks = chunk_pages([page(text)], chunk_size=1000, overlap=100)

        self.assertEqual(
            [chunk["section"] for chunk in chunks],
            ["abstract", "introduction", "results", "references"],
        )
        self.assertEqual([chunk["chunk_index"] for chunk in chunks], [0, 1, 2, 3])
        self.assertEqual("".join(chunk["text"] for chunk in chunks), text)
        self.assertTrue(chunks[-1]["text"].startswith("REFERENCES\n"))
        self.assertNotIn("REFERENCES", chunks[-2]["text"])

    def test_carries_across_pages_and_resets_at_document_boundary(self) -> None:
        pages = [
            page("2. METHODS\nFirst procedure.", number=1),
            page("Procedure continued.", number=2),
            page("No heading in another document.", document="other.pdf", number=1),
            page("Still no heading.", document="other.pdf", number=2),
        ]

        chunks = chunk_pages(pages, chunk_size=1000, overlap=0)

        self.assertEqual(
            [chunk["section"] for chunk in chunks],
            ["methods", "methods", "unknown", "unknown"],
        )

    def test_explicit_page_section_is_optional_and_carries_forward(self) -> None:
        chunks = chunk_pages([
            page("Extracted body.", section="methods"),
            page("Continued body.", number=2),
        ])

        self.assertEqual([chunk["section"] for chunk in chunks], ["methods", "methods"])

    def test_unrecognized_heading_does_not_infer_a_section(self) -> None:
        unknown = chunk_pages([page("LIMITATIONS\nNo recognized section.")])
        after_results = chunk_pages([
            page("RESULTS\nObserved result.\nLIMITATIONS\nCaveat."),
        ])

        self.assertEqual([chunk["section"] for chunk in unknown], ["unknown"])
        self.assertEqual(
            [chunk["section"] for chunk in after_results], ["results"],
        )

    def test_references_ignore_article_like_headings_but_allow_appendix(self) -> None:
        chunks = chunk_pages([
            page("REFERENCES\n[1] A title.\nDISCUSSION\nJournal text."),
            page("More citation text.", number=2),
            page("APPENDIX\nAdditional table.", number=3),
            page("RESULTS\nActual result.", document="next.pdf", number=1),
        ])

        self.assertEqual(
            [chunk["section"] for chunk in chunks],
            ["references", "references", "appendix", "results"],
        )

    def test_terminal_headings_replace_the_prior_scientific_section(self) -> None:
        text = (
            "5. CONCLUSION\nConclusion text.\n"
            "FUNDING\nGrant text.\n"
            "DECLARATION OF COMPETING INTEREST\nNone.\n"
            "ACKNOWLEDGEMENT\nThanks.\n"
            "REFERENCES\n[1] Citation."
        )

        chunks = chunk_pages([page(text)], chunk_size=1000, overlap=0)

        self.assertEqual(
            [chunk["section"] for chunk in chunks],
            [
                "conclusion",
                "funding",
                "conflicts_of_interest",
                "acknowledgments",
                "references",
            ],
        )


if __name__ == "__main__":
    unittest.main()
