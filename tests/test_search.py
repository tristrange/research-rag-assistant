import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Chunk
from app.retrieval.search import list_documents, search_chunks


class SearchTests(unittest.TestCase):
    def test_lists_distinct_document_names_in_stable_order(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as db:
            for document in ["b.pdf", "a.pdf", "b.pdf"]:
                db.add(Chunk(
                    document=document, page=1, chunk_index=0, text="Evidence",
                    embedding=[0.0] * 768,
                ))

        with patch("app.retrieval.search.SessionLocal", sessions):
            self.assertEqual(list_documents(), ["a.pdf", "b.pdf"])

    def test_exact_document_predicate_precedes_vector_ranking_and_limit(self) -> None:
        db = MagicMock()
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768):
            self.assertEqual(search_chunks("Question", limit=3, document="a.pdf"), [])

        statement = db.scalars.call_args.args[0]
        compiled = statement.compile()
        sql = str(compiled)
        self.assertLess(sql.index("WHERE chunks.document ="), sql.index("ORDER BY"))
        self.assertLess(sql.index("ORDER BY"), sql.index("LIMIT"))
        self.assertIn("a.pdf", compiled.params.values())
        self.assertIn(3, compiled.params.values())
        db.close.assert_called_once_with()

    def test_unscoped_search_keeps_corpus_wide_ranking(self) -> None:
        db = MagicMock()
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768):
            search_chunks("Question")
        statement = db.scalars.call_args.args[0]
        self.assertIsNone(statement.whereclause)


if __name__ == "__main__":
    unittest.main()
