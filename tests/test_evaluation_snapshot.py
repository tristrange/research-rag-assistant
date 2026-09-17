import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Chunk
from scripts.compare_reranking import snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(engine)
        patcher = patch("scripts.compare_reranking.SessionLocal", self.sessions)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add_chunk(self, document: str = "sample.pdf") -> None:
        with self.sessions.begin() as db:
            db.add(Chunk(document=document, page=1, chunk_index=0,
                         text="Research passage", embedding=[0.0] * 768))

    def test_missing_document_rejected(self) -> None:
        self.add_chunk("other.pdf")
        with self.assertRaisesRegex(ValueError, "No indexed chunks"):
            snapshot("sample.pdf")

    def test_duplicate_identities_rejected(self) -> None:
        self.add_chunk()
        self.add_chunk()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            snapshot("sample.pdf")

    def test_section_changes_invalidate_snapshot(self) -> None:
        self.add_chunk()
        before = snapshot("sample.pdf")
        with self.sessions.begin() as db:
            stored = db.get(Chunk, 1)
            assert stored is not None
            stored.section = "references"
        self.assertNotEqual(snapshot("sample.pdf"), before)

    def test_fingerprint_stable_and_includes_other_documents(self) -> None:
        self.add_chunk()
        before = snapshot("sample.pdf")
        self.assertEqual(snapshot("sample.pdf"), before)
        self.add_chunk("other.pdf")
        after = snapshot("sample.pdf")
        self.assertNotEqual(after["sha256"], before["sha256"])
        self.assertEqual(after["chunks_by_document"], {"sample.pdf": 1, "other.pdf": 1})


if __name__ == "__main__":
    unittest.main()
