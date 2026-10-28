"""Checks for the synthetic example PDF generator."""

import tempfile
import unittest
from pathlib import Path

import pymupdf

from scripts.generate_example_pdf import DEFAULT_OUTPUT, generate_example_pdf


class GenerateExamplePdfTests(unittest.TestCase):
    def test_default_output_is_a_distinct_synthetic_file_under_data(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT, Path("data/synthetic-portfolio-example.pdf"))

    def test_generates_a_marked_two_page_pdf_with_the_example_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example.pdf"

            result = generate_example_pdf(output)

            self.assertEqual(result, output)
            document = pymupdf.open(output)
            try:
                self.assertEqual(len(document), 2)
                text = "\n".join(page.get_text("text") for page in document)
            finally:
                document.close()
            self.assertGreaterEqual(text.count("SYNTHETIC EXAMPLE"), 2)
            self.assertIn("12 percentage points", text)
            self.assertNotIn("dropout", text.lower())

    def test_refuses_to_overwrite_and_preserves_the_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example.pdf"
            output.write_bytes(b"existing content")

            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                generate_example_pdf(output)

            self.assertEqual(output.read_bytes(), b"existing content")
