from contextlib import redirect_stdout
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import Connection, create_engine, event, select
from sqlalchemy.engine import ExecutionContext
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Chunk, DocumentIndex
from app.library import IndexedDocument, document_provenance, library_inventory, remove_document
from scripts.manage_library import main


class LibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        patcher = patch("app.library.SessionLocal", self.sessions)
        patcher.start()
        self.addCleanup(patcher.stop)
        with self.sessions.begin() as db:
            db.add_all([
                Chunk(document=document, page=page, chunk_index=index,
                      text="Synthetic paper text", embedding=[0.0] * 768)
                for document, page, index in [
                    ("a.pdf", 1, 0), ("a.pdf", 1, 1), ("a.pdf", 3, 0),
                    ("A.pdf", 2, 0), ("a%_.pdf", 1, 0), ("other paper.pdf", 1, 0),
                ]
            ])

    def test_inventory_is_sorted_and_counts_distinct_indexed_pages(self) -> None:
        self.assertEqual(library_inventory(), [
            IndexedDocument("A.pdf", 1, 1), IndexedDocument("a%_.pdf", 1, 1),
            IndexedDocument("a.pdf", 3, 2), IndexedDocument("other paper.pdf", 1, 1),
        ])

    def test_provenance_inspection_reports_unknown_and_removal_cleans_record(self) -> None:
        self.assertIsNone(document_provenance("a.pdf"))
        output = io.StringIO()
        with patch("sys.argv", ["manage_library", "provenance", "a.pdf"]), redirect_stdout(output):
            main()
        self.assertIn("Provenance unknown", output.getvalue())
        with self.sessions.begin() as db:
            db.add(DocumentIndex(
                document="a.pdf", pdf_sha256="a" * 64, embedding_model="nomic-embed-text",
                embedding_dimensions=768, extraction_version="extract-v1",
                chunking_version="chunks-v1", chunk_size=500, overlap=100,
            ))
        record = document_provenance("a.pdf")
        assert record is not None
        self.assertEqual(record["pdf_sha256"], "a" * 64)
        self.assertEqual(record["embedding_dimensions"], 768)
        output = io.StringIO()
        with patch("sys.argv", ["manage_library", "provenance", "a.pdf"]), redirect_stdout(output):
            main()
        self.assertIn("embedding_model: nomic-embed-text", output.getvalue())
        remove_document("a.pdf")
        self.assertIsNone(document_provenance("a.pdf"))

    def test_removal_matches_exact_filename_and_preserves_other_papers(self) -> None:
        self.assertEqual(remove_document("a.pdf"), 3)
        self.assertEqual([paper.document for paper in library_inventory()], ["A.pdf", "a%_.pdf", "other paper.pdf"])
        self.assertEqual(remove_document("a%_.pdf"), 1)
        self.assertEqual(remove_document("missing.pdf"), 0)
        self.assertEqual(remove_document("a.pdf"), 0)
        self.assertEqual([paper.document for paper in library_inventory()], ["A.pdf", "other paper.pdf"])

    def test_invalid_paths_and_blank_names_are_rejected_before_database_access(self) -> None:
        separators = [separator for separator in (os.sep, os.altsep) if separator]
        for document in ("", "   ", ".", "..", *(f"data{separator}a.pdf" for separator in separators)):
            with self.subTest(document=document), patch("app.library.SessionLocal") as database:
                with self.assertRaises(ValueError):
                    remove_document(document)
                database.begin.assert_not_called()

    @unittest.skipIf(os.name == "nt", "Backslashes are path separators on Windows")
    def test_cli_removes_posix_backslash_filename_and_preserves_source(self) -> None:
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "study\\draft.pdf"
            pdf.write_bytes(b"Original PDF bytes")
            # Match the indexer's filename identity, including literal backslashes.
            with self.sessions.begin() as db:
                db.add(Chunk(document=pdf.name, page=1, chunk_index=0,
                             text="Synthetic paper text", embedding=[0.0] * 768))
            self.assertIn(pdf.name, [paper.document for paper in library_inventory()])
            output = io.StringIO()
            before = library_inventory()
            with patch("sys.argv", ["manage_library", "remove", pdf.name]), redirect_stdout(output):
                main()
            self.assertEqual(library_inventory(), before)
            self.assertIn("Would remove 1 chunks", output.getvalue())
            with patch("sys.argv", ["manage_library", "remove", pdf.name, "--yes"]), redirect_stdout(output):
                main()
            self.assertEqual(library_inventory(), [paper for paper in before if paper.document != pdf.name])
            self.assertEqual(pdf.read_bytes(), b"Original PDF bytes")

    def test_original_pdf_is_preserved(self) -> None:
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "a.pdf"
            pdf.write_bytes(b"Original PDF bytes")
            remove_document(pdf.name)
            self.assertEqual(pdf.read_bytes(), b"Original PDF bytes")

    def test_failure_after_delete_rolls_back_all_removed_chunks(self) -> None:
        def fail_after_delete(
            connection: Connection, cursor: object, statement: str,
            parameters: object, context: ExecutionContext, many: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("DELETE"):
                raise RuntimeError("Simulated failure after deletion")

        before = library_inventory()
        event.listen(self.engine, "after_cursor_execute", fail_after_delete)
        try:
            with self.assertRaises(RuntimeError):
                remove_document("a.pdf")
        finally:
            event.remove(self.engine, "after_cursor_execute", fail_after_delete)
        self.assertEqual(library_inventory(), before)
        with self.sessions() as db:
            self.assertEqual(len(list(db.scalars(select(Chunk)))), 6)

    def test_cli_previews_removal_and_requires_yes_to_apply(self) -> None:
        output = io.StringIO()
        with patch("sys.argv", ["manage_library", "remove", "other paper.pdf"]), redirect_stdout(output):
            main()
        self.assertIn("Would remove 1 chunks", output.getvalue())
        self.assertIn("--yes", output.getvalue())
        self.assertIn("other paper.pdf", [paper.document for paper in library_inventory()])
        with patch("sys.argv", ["manage_library", "remove", "other paper.pdf", "--yes"]), redirect_stdout(output):
            main()
        self.assertNotIn("other paper.pdf", [paper.document for paper in library_inventory()])
        self.assertIn("original PDF was not deleted", output.getvalue())

    def test_cli_reports_missing_document_without_deleting_anything(self) -> None:
        before = library_inventory()
        for suffix in ([], ["--yes"]):
            with patch("sys.argv", ["manage_library", "remove", "missing.pdf", *suffix]):
                with self.assertRaisesRegex(SystemExit, "No matching indexed paper"):
                    main()
        self.assertEqual(library_inventory(), before)

    def test_cli_lists_inventory_and_handles_empty_library(self) -> None:
        output = io.StringIO()
        with patch("sys.argv", ["manage_library", "list"]), redirect_stdout(output):
            main()
        self.assertIn("a.pdf: 3 chunks, 2 indexed pages", output.getvalue())
        with patch("sys.argv", ["manage_library", "list"]), \
                patch("scripts.manage_library.library_inventory", return_value=[]), redirect_stdout(output):
            main()
        self.assertIn("No papers are indexed", output.getvalue())

    def test_cli_database_error_has_guidance_without_exception_details(self) -> None:
        with patch("sys.argv", ["manage_library", "list"]), patch(
            "scripts.manage_library.library_inventory", side_effect=OperationalError("private SQL", {}, Exception("secret-password")),
        ):
            with self.assertRaises(SystemExit) as caught:
                main()
        self.assertIn("scripts.init_db", str(caught.exception))
        self.assertNotIn("secret-password", str(caught.exception))
        self.assertNotIn("private SQL", str(caught.exception))
