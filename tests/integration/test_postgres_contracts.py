"""Exercise production SQL with synthetic data, never an existing paper index."""

import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import Engine, create_engine, make_url, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import Chunk
from app.retrieval import search
from scripts import init_db


TEST_URL = os.environ.get("RAG_TEST_POSTGRES_URL")


def vector(x: float, y: float = 0.0) -> list[float]:
    return [x, y, *([0.0] * 766)]


@unittest.skipUnless(TEST_URL, "Set RAG_TEST_POSTGRES_URL to run PostgreSQL contracts")
class PostgresContracts(unittest.TestCase):
    control: Engine
    engine: Engine

    @classmethod
    def setUpClass(cls) -> None:
        assert TEST_URL is not None
        url = make_url(TEST_URL)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("RAG_TEST_POSTGRES_URL must use postgresql+psycopg")
        cls.control = create_engine(url, isolation_level="AUTOCOMMIT")
        cls.addClassCleanup(cls.control.dispose)

    def setUp(self) -> None:
        # PostgreSQL cannot CREATE DATABASE inside a transaction. The controller
        # is used only for lifecycle SQL; production tables live in a new DB.
        name = f"rag_contract_{uuid4().hex}"
        with self.control.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
        self.addCleanup(self.drop_database, name)
        self.engine = create_engine(self.control.url.set(database=name))
        self.addCleanup(self.engine.dispose)
        self.sessions = sessionmaker(self.engine)

    def drop_database(self, name: str) -> None:
        with self.control.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))

    def initialize(self) -> None:
        with patch.object(init_db, "engine", self.engine):
            init_db.initialize_database()

    def add_chunk(
        self, document: str, embedding: list[float], *,
        section: str = "results", chunk_index: int = 0,
    ) -> int:
        with self.sessions.begin() as db:
            chunk = Chunk(document=document, page=1, chunk_index=chunk_index,
                          text=f"Synthetic passage {document}/{chunk_index}",
                          section=section, embedding=embedding)
            db.add(chunk)
            db.flush()
            return chunk.id

    def legacy_schema(self, *, nullable_section: bool = False) -> None:
        section_column = ", section TEXT" if nullable_section else ""
        with self.engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION vector"))
            connection.execute(text(
                "CREATE TABLE chunks (id SERIAL PRIMARY KEY, document TEXT NOT NULL, "
                "page INTEGER NOT NULL, chunk_index INTEGER NOT NULL, text TEXT NOT NULL, "
                f"embedding vector(768) NOT NULL{section_column})"
            ))
            connection.execute(text(
                "INSERT INTO chunks (document, page, chunk_index, text, embedding) "
                "VALUES ('legacy.pdf', 3, 0, 'Original synthetic passage', CAST(:vector AS vector))"
            ), {"vector": json.dumps(vector(1.0))})

    def test_fresh_initialization_is_repeatable_and_preserves_rows(self) -> None:
        self.initialize()
        identifier = self.add_chunk("fresh.pdf", vector(1.0))
        self.initialize()
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text(
                "SELECT extname FROM pg_extension WHERE extname = 'vector'"
            )), "vector")
            self.assertEqual(connection.scalar(text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            )), "vector(768)")
        with self.sessions() as db:
            chunks = list(db.scalars(select(Chunk)))
            self.assertEqual([(c.id, c.document, c.section) for c in chunks],
                             [(identifier, "fresh.pdf", "results")])
            self.assertEqual(list(chunks[0].embedding), vector(1.0))

    def test_legacy_section_migration_preserves_text_locations_and_vectors(self) -> None:
        self.legacy_schema()
        self.initialize()
        self.initialize()
        with self.sessions() as db:
            chunk = db.scalars(select(Chunk)).one()
            self.assertEqual((chunk.id, chunk.document, chunk.page, chunk.chunk_index,
                              chunk.text, chunk.section),
                             (1, "legacy.pdf", 3, 0, "Original synthetic passage", "unknown"))
            self.assertEqual(list(chunk.embedding), vector(1.0))

    def test_nullable_section_migration_keeps_labels_and_enforces_default(self) -> None:
        self.legacy_schema(nullable_section=True)
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO chunks (document, page, chunk_index, text, embedding, section) "
                "SELECT document, page, 1, text, embedding, 'results' FROM chunks"
            ))
        self.initialize()
        self.initialize()
        with self.engine.begin() as connection:
            self.assertEqual(list(connection.scalars(text(
                "SELECT section FROM chunks ORDER BY id"
            ))), ["unknown", "results"])
            self.assertEqual(connection.scalar(text(
                "INSERT INTO chunks (document, page, chunk_index, text, embedding) "
                "SELECT document, page, 2, text, embedding FROM chunks LIMIT 1 RETURNING section"
            )), "unknown")
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(text("UPDATE chunks SET section = NULL WHERE id = 1"))
        with self.sessions() as db:
            chunk = db.get(Chunk, 1)
            assert chunk is not None
            self.assertEqual(chunk.section, "unknown")

    def test_cosine_ranking_cutoff_and_ties_use_production_search(self) -> None:
        self.initialize()
        self.add_chunk("opposite.pdf", vector(-1.0))
        self.add_chunk("orthogonal.pdf", vector(0.0, 1.0))
        diagonal = self.add_chunk("diagonal.pdf", vector(1.0, 1.0))
        first = self.add_chunk("first.pdf", vector(1.0))
        second = self.add_chunk("second.pdf", vector(1.0))
        with patch.object(search, "SessionLocal", self.sessions), \
                patch.object(search, "embed_text", return_value=vector(1.0)):
            self.assertEqual([c.id for c in search.search_chunks("Synthetic question", 3)],
                             [first, second, diagonal])

    def test_exact_document_and_section_filters_apply_before_limit(self) -> None:
        self.initialize()
        self.add_chunk("other.pdf", vector(1.0))
        self.add_chunk("Paper.pdf", vector(1.0))
        self.add_chunk("paper.pdf", vector(1.0), section="references")
        self.add_chunk("paper.pdf", vector(1.0, 1.0), section="abstract", chunk_index=1)
        result = self.add_chunk("paper.pdf", vector(0.0, 1.0), chunk_index=2)
        with patch.object(search, "SessionLocal", self.sessions), \
                patch.object(search, "embed_text", return_value=vector(1.0)) as embed:
            found = search.search_chunks("Synthetic question", 1, document="paper.pdf",
                                         sections=("results",))
            self.assertEqual([c.id for c in found], [result])
            self.assertCountEqual(search.list_documents(), ["Paper.pdf", "other.pdf", "paper.pdf"])
            embed.reset_mock()
            self.assertEqual(search.search_chunks("Synthetic question", 1,
                                                 document="absent.pdf"), [])
            embed.assert_not_called()

    def test_postgres_rejects_wrong_vector_dimensions_without_losing_rows(self) -> None:
        self.initialize()
        identifier = self.add_chunk("preserved.pdf", vector(1.0))
        # Bypass the Python Vector binder so this exercises server enforcement.
        with self.assertRaises(DBAPIError) as failure, self.engine.begin() as connection:
            connection.execute(text("UPDATE chunks SET embedding = '[1,0]'::vector"))
        self.assertIn("expected 768 dimensions, not 2", str(failure.exception.orig))
        with self.sessions() as db:
            chunk = db.get(Chunk, identifier)
            assert chunk is not None
            self.assertEqual(list(chunk.embedding), vector(1.0))


if __name__ == "__main__":
    unittest.main()
