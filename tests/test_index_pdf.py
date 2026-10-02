from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
import pymupdf
from sqlalchemy import Connection, create_engine, event, select
from sqlalchemy.engine import ExecutionContext

from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Chunk
from app.embeddings import OLLAMA_EMBED_URL, embed_text
from app.ingestion import indexing
from app.ingestion.pdf import extract_pages
from app.llm.errors import OllamaResponseError
from app.types import PageData
from scripts import index_pdf as index_cli


class IndexPdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.pages: list[PageData] = [{"document": "sample.pdf", "page": 1, "text": "Original text"}]
        for target, replacement in [
            ("SessionLocal", self.sessions),
            ("extract_pages", lambda _, **kwargs: self.pages),
            ("embed_text", lambda _: [0.0] * 768),
        ]:
            patcher = patch.object(indexing, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def contents(self) -> list[tuple[str, str]]:
        with self.sessions() as db:
            return sorted(
                (chunk.document, chunk.text)
                for chunk in db.scalars(select(Chunk))
            )

    def sections(self) -> list[str]:
        with self.sessions() as db:
            return list(db.scalars(select(Chunk.section).order_by(Chunk.id)))

    def test_repeated_indexing_does_not_duplicate_chunks(self) -> None:
        self.assertEqual(indexing.index_pdf(), 1)
        self.assertEqual(indexing.index_pdf(), 1)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])
        self.assertEqual(self.sections(), ["unknown"])

    def test_persists_recognized_section_metadata(self) -> None:
        self.pages[0]["text"] = "3. RESULTS\nObserved result."

        self.assertEqual(indexing.index_pdf(), 1)

        self.assertEqual(self.sections(), ["results"])

    def test_replacement_removes_stale_chunks_and_preserves_other_documents(self) -> None:
        self.pages[0]["text"] = "x" * 900
        self.assertGreater(indexing.index_pdf(), 1)
        with self.sessions.begin() as db:
            db.add(Chunk(document="other.pdf", page=1, chunk_index=0,
                         text="Other document", embedding=[0.0] * 768))
        self.pages[0]["text"] = "Updated text"
        self.assertEqual(indexing.index_pdf(), 1)
        self.assertEqual(self.contents(), [
            ("other.pdf", "Other document"), ("sample.pdf", "Updated text"),
        ])

    def test_embedding_failure_preserves_existing_chunks(self) -> None:
        indexing.index_pdf()
        messages: list[str] = []
        with patch.object(indexing, "embed_text", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                indexing.index_pdf(progress=messages.append)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])
        self.assertEqual(messages[-1], "Embedding chunks: 0/1")
        self.assertNotIn("Saving index…", messages)

    def test_malformed_embedding_keeps_index_and_cli_reports_safe_failure(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "Updated text"
        malformed = httpx.Response(200, request=httpx.Request("POST", OLLAMA_EMBED_URL),
                                  json={"embeddings": [["private provider output"]]})
        with patch.object(indexing, "embed_text", embed_text), patch("httpx.post", return_value=malformed):
            with self.assertRaises(OllamaResponseError):
                indexing.index_pdf()
            with TemporaryDirectory() as directory:
                pdf = Path(directory) / "sample.pdf"
                pdf.touch()
                output = io.StringIO()
                with patch("sys.argv", ["index_pdf", str(pdf)]), redirect_stderr(output), redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as exit_result:
                        index_cli.main()
        self.assertEqual(exit_result.exception.code, 1)
        self.assertIn("invalid embedding response", output.getvalue())
        self.assertIn("existing index was not replaced", output.getvalue())
        self.assertNotIn("private provider output", output.getvalue())
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_progress_reports_completed_embeddings_before_index_replacement(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "Updated text"
        messages: list[str] = []

        def observe(message: str) -> None:
            messages.append(message)
            self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

        self.assertEqual(indexing.index_pdf(progress=observe), 1)
        self.assertEqual(messages, [
            "Reading sample.pdf…", "Read 1 PDF pages. Preparing chunks…",
            "Embedding chunks: 0/1", "Embedding chunks: 1/1", "Saving index…",
        ])
        self.assertEqual(self.contents(), [("sample.pdf", "Updated text")])

    def test_chunk_progress_is_bounded_and_handles_an_empty_pdf(self) -> None:
        self.pages[0]["text"] = "x" * 20_000
        messages: list[str] = []
        count = indexing.index_pdf(progress=messages.append)
        self.assertGreater(count, 10)
        embedding_messages = [message for message in messages if message.startswith("Embedding chunks:")]
        self.assertLessEqual(len(embedding_messages), 11)
        self.assertEqual(embedding_messages[-1], f"Embedding chunks: {count}/{count}")
        self.pages = []
        messages.clear()
        self.assertEqual(indexing.index_pdf(progress=messages.append), 0)
        self.assertIn("Embedding chunks: 0/0", messages)
        self.assertEqual(messages[-1], "Saving index…")

    def test_oversized_pdf_is_rejected_before_embedding_and_keeps_index(self) -> None:
        indexing.index_pdf()
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "sample.pdf"
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "Text longer than the test limit")
            document.save(paper)
            document.close()

            with patch.object(indexing, "extract_pages", extract_pages), patch.object(indexing, "MAX_PAGE_CHARS", 10), patch.object(indexing, "embed_text") as embedder:
                with self.assertRaisesRegex(ValueError, "PDF page 1 exceeds"):
                    indexing.index_pdf(str(paper))
                embedder.assert_not_called()
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_too_many_blank_pages_are_rejected_before_embedding(self) -> None:
        indexing.index_pdf()
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "sample.pdf"
            document = pymupdf.open()
            for _ in range(3):
                document.new_page()
            document.save(paper)
            document.close()

            with patch.object(indexing, "extract_pages", extract_pages), patch.object(indexing, "MAX_PDF_PAGES", 2), patch.object(indexing, "embed_text") as embedder:
                with self.assertRaisesRegex(ValueError, "2-page limit"):
                    indexing.index_pdf(str(paper))
                embedder.assert_not_called()
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_excess_chunks_are_rejected_before_embedding_and_keep_index(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "x" * 2000

        with patch.object(indexing, "MAX_CHUNKS", 1), patch.object(indexing, "embed_text") as embedder:
            with self.assertRaisesRegex(ValueError, "1-chunk limit"):
                indexing.index_pdf()
            embedder.assert_not_called()
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_insert_failure_rolls_back_deletion(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "Updated text"

        def reject_insert(
            connection: Connection, cursor: object, statement: str,
            parameters: object, context: ExecutionContext, many: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("INSERT"):
                raise RuntimeError("insert failed")

        event.listen(self.engine, "before_cursor_execute", reject_insert)
        try:
            with self.assertRaisesRegex(RuntimeError, "insert failed"):
                indexing.index_pdf()
        finally:
            event.remove(self.engine, "before_cursor_execute", reject_insert)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_empty_document_removes_its_stale_chunks(self) -> None:
        indexing.index_pdf()
        self.pages = []
        self.assertEqual(indexing.index_pdf(), 0)
        self.assertEqual(self.contents(), [])


class IndexCliTests(unittest.TestCase):
    def test_arbitrary_pdf_path_reaches_indexer(self) -> None:
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "another paper.pdf"
            paper.write_bytes(b"fixture")
            with patch("sys.argv", ["index_pdf", str(paper)]), patch.object(index_cli, "index_pdf", return_value=7) as indexer, redirect_stdout(io.StringIO()) as output:
                index_cli.main()
            indexer.assert_called_once_with(str(paper), progress=index_cli.print_progress)
            self.assertIn("7 chunks from another paper.pdf", output.getvalue())

    def test_failed_indexing_never_prints_completion(self) -> None:
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "paper.pdf"
            paper.write_bytes(b"fixture")
            with patch("sys.argv", ["index_pdf", str(paper)]), \
                    patch.object(index_cli, "index_pdf", side_effect=RuntimeError("save failed")), \
                    redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(RuntimeError, "save failed"):
                    index_cli.main()
            self.assertNotIn("Indexed", output.getvalue())

    def test_bad_input_never_calls_indexer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "paper.txt"
            text.write_text("not a PDF")
            for path in [root / "missing.pdf", root, text]:
                with self.subTest(path=path), patch("sys.argv", ["index_pdf", str(path)]), patch.object(index_cli, "index_pdf") as indexer, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    index_cli.main()
                indexer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
