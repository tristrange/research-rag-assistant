import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Chunk
from scripts import index_pdf


class IndexPdfTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.pages = [{"document": "sample.pdf", "page": 1, "text": "Original text"}]
        for target, replacement in [
            ("SessionLocal", self.sessions),
            ("extract_pages", lambda _: self.pages),
            ("embed_text", lambda _: [0.0] * 768),
        ]:
            patcher = patch.object(index_pdf, target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def contents(self):
        with self.sessions() as db:
            return sorted(
                (chunk.document, chunk.text)
                for chunk in db.scalars(select(Chunk))
            )

    def test_repeated_indexing_does_not_duplicate_chunks(self):
        self.assertEqual(index_pdf.index_pdf(), 1)
        self.assertEqual(index_pdf.index_pdf(), 1)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_replacement_removes_stale_chunks_and_preserves_other_documents(self):
        self.pages[0]["text"] = "x" * 900
        self.assertGreater(index_pdf.index_pdf(), 1)
        with self.sessions.begin() as db:
            db.add(Chunk(document="other.pdf", page=1, chunk_index=0,
                         text="Other document", embedding=[0.0] * 768))
        self.pages[0]["text"] = "Updated text"
        self.assertEqual(index_pdf.index_pdf(), 1)
        self.assertEqual(self.contents(), [
            ("other.pdf", "Other document"), ("sample.pdf", "Updated text"),
        ])

    def test_embedding_failure_preserves_existing_chunks(self):
        index_pdf.index_pdf()
        with patch.object(index_pdf, "embed_text", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                index_pdf.index_pdf()
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_insert_failure_rolls_back_deletion(self):
        index_pdf.index_pdf()
        self.pages[0]["text"] = "Updated text"

        def reject_insert(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("INSERT"):
                raise RuntimeError("insert failed")

        event.listen(self.engine, "before_cursor_execute", reject_insert)
        try:
            with self.assertRaisesRegex(RuntimeError, "insert failed"):
                index_pdf.index_pdf()
        finally:
            event.remove(self.engine, "before_cursor_execute", reject_insert)
        self.assertEqual(self.contents(), [("sample.pdf", "Original text")])

    def test_empty_document_removes_its_stale_chunks(self):
        index_pdf.index_pdf()
        self.pages = []
        self.assertEqual(index_pdf.index_pdf(), 0)
        self.assertEqual(self.contents(), [])


if __name__ == "__main__":
    unittest.main()
