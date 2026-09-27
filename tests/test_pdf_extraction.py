from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from app.ingestion.pdf import extract_pages


class PdfExtractionBudgetTests(unittest.TestCase):
    def test_default_extraction_preserves_pages_and_total_limit_rejects(self) -> None:
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "paper.pdf"
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "First page")
            document.new_page().insert_text((72, 72), "Second page")
            document.save(paper)
            document.close()

            pages = extract_pages(str(paper))
            self.assertEqual([page["text"] for page in pages], ["First page", "Second page"])
            self.assertEqual([page["page"] for page in pages], [1, 2])
            self.assertTrue(all(page["document"] == "paper.pdf" for page in pages))
            with self.assertRaisesRegex(ValueError, "character text limit"):
                extract_pages(str(paper), max_total_chars=len(pages[0]["text"]) + 1)


if __name__ == "__main__":
    unittest.main()
