import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.index_contract import IndexCompatibilityError
from app.db.models import Chunk
from app.retrieval.search import (
    QuestionEmbedding,
    list_documents,
    search_by_embedding,
    search_chunks,
)


class SearchTests(unittest.TestCase):
    def test_lists_distinct_document_names_in_stable_order(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as db:
            for index, document in enumerate(["b.pdf", "a.pdf", "b.pdf"]):
                db.add(Chunk(
                    document=document, page=1, chunk_index=index, text="Evidence",
                    embedding=[0.0] * 768,
                ))

        with patch("app.retrieval.search.SessionLocal", sessions):
            self.assertEqual(list_documents(), ["a.pdf", "b.pdf"])

    def test_exact_document_predicate_precedes_vector_ranking_and_limit(self) -> None:
        db = MagicMock()
        db.scalar.side_effect = [None, 1, None]
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

    def test_missing_selected_document_skips_embedding(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine)
        with patch("app.retrieval.search.SessionLocal", sessions), \
                patch("app.retrieval.search.embed_text", side_effect=AssertionError("must not embed")) as embed:
            self.assertEqual(search_chunks("Question", document="missing.pdf"), [])
        embed.assert_not_called()

    def test_unscoped_search_keeps_corpus_wide_ranking(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768):
            search_chunks("Question")
        statement = db.scalars.call_args.args[0]
        self.assertIsNone(statement.whereclause)

    def test_section_filter_limits_ranked_candidates(self) -> None:
        db = MagicMock()
        db.scalar.side_effect = [None, 1, None]
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768):
            search_chunks("Findings", document="a.pdf", sections=("abstract", "discussion"))
        compiled = db.scalars.call_args.args[0].compile()
        sql = str(compiled)
        self.assertIn("chunks.document =", sql)
        self.assertIn("chunks.section IN", sql)
        self.assertLess(sql.index("chunks.section IN"), sql.index("ORDER BY"))
        self.assertEqual(compiled.params["section_1"], ["abstract", "discussion"])

    def test_question_embedding_is_reused_across_scopes_but_fresh_per_instance(self) -> None:
        db = MagicMock()
        db.scalar.side_effect = [None, 1, None, None, 1, None, None, None]
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768) as embed:
            shared = QuestionEmbedding("Question")
            search_by_embedding(shared, document="a.pdf", sections=("abstract",))
            search_by_embedding(shared, document="b.pdf", sections=("discussion",))

            fresh = QuestionEmbedding("Question")
            search_by_embedding(fresh)

        self.assertEqual(embed.call_count, 2)
        self.assertEqual([call.args[0] for call in embed.call_args_list], ["Question", "Question"])

    def test_different_questions_are_not_shared(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = []
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768) as embed:
            search_by_embedding(QuestionEmbedding("First question"))
            search_by_embedding(QuestionEmbedding("Second question"))

        self.assertEqual(
            [call.args[0] for call in embed.call_args_list],
            ["First question", "Second question"],
        )

    def test_incompatible_corpus_skips_embedding(self) -> None:
        db = MagicMock()
        db.scalar.side_effect = IndexCompatibilityError("incompatible")
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", side_effect=AssertionError("must not embed")) as embed:
            with self.assertRaises(IndexCompatibilityError):
                search_by_embedding(QuestionEmbedding("Question"))
        embed.assert_not_called()
        db.scalars.assert_not_called()

    def test_failed_embedding_is_retried_and_exception_propagates(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = []
        embedding = QuestionEmbedding("Question")
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch(
                    "app.retrieval.search.embed_text",
                    side_effect=[RuntimeError("embedding failed"), [0.0] * 768],
                ) as embed:
            with self.assertRaisesRegex(RuntimeError, "embedding failed"):
                search_by_embedding(embedding)
            search_by_embedding(embedding)

        self.assertEqual(embed.call_count, 2)
        db.scalars.assert_called_once()

    def test_first_inference_happens_after_read_lock_transaction_is_released(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = []
        events: list[str] = []

        def embed_after_rollback(question: str) -> list[float]:
            events.append("embed")
            self.assertEqual(question, "Question")
            self.assertEqual(events, ["lock", "rollback", "embed"])
            return [0.0] * 768

        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.lock_index", side_effect=lambda *args, **kwargs: events.append("lock")), \
                patch("app.retrieval.search.embed_text", side_effect=embed_after_rollback):
            db.rollback.side_effect = lambda: events.append("rollback")
            search_by_embedding(QuestionEmbedding("Question"))

        self.assertEqual(events, ["lock", "rollback", "embed", "lock"])

    def test_profile_change_blocks_cached_vector_from_ranking(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = []
        with patch("app.embeddings.EMBEDDING_MODEL", "model-a"), \
                patch("app.embeddings.EMBEDDING_DIMENSIONS", 768), \
                patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768) as embed:
            embedding = QuestionEmbedding("Question")
            search_by_embedding(embedding)
            db.scalars.reset_mock()

            with patch("app.embeddings.EMBEDDING_MODEL", "model-b"):
                with self.assertRaises(IndexCompatibilityError):
                    search_by_embedding(embedding)

        embed.assert_called_once_with("Question")
        db.scalars.assert_not_called()

    def test_search_chunks_rejects_embedding_for_a_different_question_before_services(self) -> None:
        with patch("app.retrieval.search.SessionLocal") as session, \
                patch("app.retrieval.search.embed_text") as embed:
            with self.assertRaises(ValueError):
                search_chunks("Different question", query_embedding=QuestionEmbedding("Original question"))

        session.assert_not_called()
        embed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
