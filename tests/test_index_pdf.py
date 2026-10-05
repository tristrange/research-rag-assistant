from contextlib import redirect_stderr, redirect_stdout
import io
import hashlib
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
from app.db.models import Chunk, DocumentIndex
from app.embeddings import OLLAMA_EMBED_URL, embed_texts
from app.ingestion import indexing
from app.ingestion.pdf import extract_pages
from app.llm.errors import OllamaResponseError
from app.types import PageData
from scripts import index_pdf as index_cli


REAL_PDF_CHECKSUM = indexing.pdf_checksum


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
            ("embed_texts", lambda texts, *, client=None: [[0.0] * 768 for _ in texts]),
            ("pdf_checksum", lambda _: "0" * 64),
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

    def document_index(self) -> tuple[object, ...] | None:
        with self.sessions() as db:
            record = db.get(DocumentIndex, "sample.pdf")
            if record is None:
                return None
            return (
                record.pdf_sha256, record.embedding_model, record.embedding_dimensions,
                record.extraction_version, record.chunking_version,
                record.chunk_size, record.overlap,
            )

    def ordered_chunks(self) -> list[Chunk]:
        with self.sessions() as db:
            return list(db.scalars(select(Chunk).order_by(Chunk.id)))

    def test_repeated_indexing_does_not_duplicate_chunks(self) -> None:
        self.assertEqual(indexing.index_pdf(), 1)
        self.assertEqual(indexing.index_pdf(), 1)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])
        self.assertEqual(self.sections(), ["unknown"])

    def test_saves_pdf_and_processing_provenance_with_chunks(self) -> None:
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "sample.pdf"
            paper.write_bytes(b"synthetic PDF bytes")
            # Exercise real checksum I/O, while extraction/embedding stay stubbed.
            with patch.object(indexing, "pdf_checksum", REAL_PDF_CHECKSUM):
                indexing.index_pdf(str(paper))
            with self.sessions() as db:
                record = db.get(DocumentIndex, "sample.pdf")
                assert record is not None
                self.assertEqual(record.pdf_sha256, hashlib.sha256(paper.read_bytes()).hexdigest())
                self.assertEqual((record.embedding_model, record.embedding_dimensions), ("nomic-embed-text", 768))
                self.assertEqual((record.chunk_size, record.overlap), (500, 100))
                self.assertEqual(record.extraction_version, indexing.EXTRACTION_VERSION)
                self.assertEqual(record.chunking_version, indexing.CHUNKING_VERSION)

    def test_changed_pdf_does_not_replace_existing_provenance_or_chunks(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "Changed text"
        for hashes in (["1" * 64, "2" * 64], ["1" * 64, "1" * 64, "2" * 64]):
            with self.subTest(hashes=hashes), patch.object(indexing, "pdf_checksum", side_effect=hashes):
                with self.assertRaisesRegex(ValueError, "PDF.*changed"):
                    indexing.index_pdf()
            self.assertEqual(self.contents(), [("sample.pdf", "Original text")])
            with self.sessions() as db:
                record = db.get(DocumentIndex, "sample.pdf")
                assert record is not None
                self.assertEqual(record.pdf_sha256, "0" * 64)

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
        with patch.object(indexing, "embed_texts", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                indexing.index_pdf(progress=messages.append)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])
        with self.sessions() as db:
            self.assertIsNotNone(db.get(DocumentIndex, "sample.pdf"))
        self.assertEqual(messages[-1], "Embedding chunks: 0/1")
        self.assertNotIn("Saving index…", messages)

    def test_malformed_embedding_keeps_index_and_cli_reports_safe_failure(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "Updated text"
        malformed = httpx.Response(200, request=httpx.Request("POST", OLLAMA_EMBED_URL),
                                  json={"embeddings": [["private provider output"]]})
        with patch.object(indexing, "embed_texts", embed_texts), patch("httpx.Client.post", return_value=malformed):
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

    def test_batches_preserve_page_order_and_partial_final_batch(self) -> None:
        self.pages = [
            {"document": "sample.pdf", "page": page, "text": f"Page {page} unique content."}
            for page in range(1, 19)
        ]
        requests: list[list[str]] = []
        embedded = 0

        def embed_batch(texts: list[str], *, client: httpx.Client | None = None) -> list[list[float]]:
            nonlocal embedded
            self.assertIsNotNone(client)
            requests.append(texts)
            vectors: list[list[float]] = []
            for _ in texts:
                vectors.append([float(embedded)] * 768)
                embedded += 1
            return vectors

        with patch.object(indexing, "embed_texts", side_effect=embed_batch):
            self.assertEqual(indexing.index_pdf(), 18)

        expected_texts = [f"Page {page} unique content." for page in range(1, 19)]
        self.assertEqual([len(request) for request in requests], [16, 2])
        self.assertEqual([text for request in requests for text in request], expected_texts)
        rows = self.ordered_chunks()
        self.assertEqual([(row.page, row.text) for row in rows], list(enumerate(expected_texts, start=1)))
        self.assertEqual([row.embedding[0] for row in rows], [float(i) for i in range(18)])

    def test_owned_client_is_reused_and_closed_on_success_and_failure(self) -> None:
        self.pages = [
            {"document": "sample.pdf", "page": page, "text": f"Page {page} unique content."}
            for page in range(1, 19)
        ]
        for fail in (False, True):
            with self.subTest(fail=fail):
                client_instance = object()
                calls = 0

                def embed_batch(texts: list[str], *, client: httpx.Client | None = None) -> list[list[float]]:
                    nonlocal calls
                    calls += 1
                    if fail and calls == 2:
                        raise RuntimeError("batch failed")
                    return [[0.0] * 768 for _ in texts]

                with patch("httpx.Client") as client_factory, \
                        patch.object(
                            indexing,
                            "embed_texts",
                            side_effect=embed_batch,
                        ) as embedder:
                    client_factory.return_value.__enter__.return_value = client_instance
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "batch failed"):
                            indexing.index_pdf()
                    else:
                        self.assertEqual(indexing.index_pdf(), 18)
                    client_factory.assert_called_once_with()
                    client_factory.return_value.__enter__.assert_called_once_with()
                    client_factory.return_value.__exit__.assert_called_once()
                    self.assertEqual(embedder.call_count, 2)
                    self.assertTrue(all(call.kwargs["client"] is client_instance for call in embedder.call_args_list))

    def test_later_batch_failure_preserves_chunks_and_provenance(self) -> None:
        indexing.index_pdf()
        original_chunks = [(row.page, row.text, row.embedding) for row in self.ordered_chunks()]
        original_index = self.document_index()
        self.pages = [
            {"document": "sample.pdf", "page": page, "text": f"Replacement page {page}."}
            for page in range(1, 19)
        ]
        messages: list[str] = []
        calls = 0

        def fail_second_batch(texts: list[str], *, client: httpx.Client | None = None) -> list[list[float]]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OllamaResponseError("embedding")
            return [[1.0] * 768 for _ in texts]

        with patch.object(indexing, "embed_texts", side_effect=fail_second_batch):
            with self.assertRaises(OllamaResponseError):
                indexing.index_pdf(progress=messages.append)

        self.assertEqual(calls, 2)
        self.assertEqual([(row.page, row.text, row.embedding) for row in self.ordered_chunks()], original_chunks)
        self.assertEqual(self.document_index(), original_index)
        self.assertEqual(
            [message for message in messages if message.startswith("Embedding chunks:")],
            ["Embedding chunks: 0/18", "Embedding chunks: 16/18"],
        )
        self.assertNotIn("Saving index…", messages)

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
        with patch("httpx.Client") as client_factory, patch.object(indexing, "embed_texts") as embedder:
            self.assertEqual(indexing.index_pdf(progress=messages.append), 0)
        client_factory.assert_not_called()
        embedder.assert_not_called()
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

            with patch.object(indexing, "extract_pages", extract_pages), patch.object(indexing, "MAX_PAGE_CHARS", 10), patch.object(indexing, "embed_texts") as embedder:
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

            with patch.object(indexing, "extract_pages", extract_pages), patch.object(indexing, "MAX_PDF_PAGES", 2), patch.object(indexing, "embed_texts") as embedder:
                with self.assertRaisesRegex(ValueError, "2-page limit"):
                    indexing.index_pdf(str(paper))
                embedder.assert_not_called()
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_excess_chunks_are_rejected_before_embedding_and_keep_index(self) -> None:
        indexing.index_pdf()
        self.pages[0]["text"] = "x" * 2000

        with patch.object(indexing, "MAX_CHUNKS", 1), patch.object(indexing, "embed_texts") as embedder:
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
        with self.sessions() as db:
            record = db.get(DocumentIndex, "sample.pdf")
            assert record is not None
            self.assertEqual(record.pdf_sha256, "0" * 64)

    def test_empty_document_removes_its_stale_chunks(self) -> None:
        indexing.index_pdf()
        self.pages = []
        self.assertEqual(indexing.index_pdf(), 0)
        self.assertEqual(self.contents(), [])
        with self.sessions() as db:
            self.assertIsNone(db.get(DocumentIndex, "sample.pdf"))


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
