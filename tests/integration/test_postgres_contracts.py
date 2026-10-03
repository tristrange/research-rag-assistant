"""Exercise production SQL with synthetic data, never an existing paper index."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from collections.abc import Callable
from typing import Literal
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import Engine, create_engine, make_url, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.index_contract import (
    IndexCompatibilityError,
    embedding_profile,
    lock_index,
    require_compatible_index,
)
from app.db.models import Chunk, DocumentIndex
from app.ingestion import indexing
from app.library import remove_document
from app.retrieval import search
from app.types import PageData
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
        model, dimensions = embedding_profile()
        with self.sessions.begin() as db:
            if db.get(DocumentIndex, document) is None:
                db.add(DocumentIndex(
                    document=document,
                    pdf_sha256="0" * 64,
                    embedding_model=model,
                    embedding_dimensions=dimensions,
                    extraction_version=indexing.EXTRACTION_VERSION,
                    chunking_version=indexing.CHUNKING_VERSION,
                    chunk_size=indexing.CHUNK_SIZE,
                    overlap=indexing.OVERLAP,
                ))
            chunk = Chunk(document=document, page=1, chunk_index=chunk_index,
                          text=f"Synthetic passage {document}/{chunk_index}",
                          section=section, embedding=embedding)
            db.add(chunk)
            db.flush()
            return chunk.id

    def legacy_schema(
        self, *, engine: Engine | None = None, nullable_section: bool = False,
    ) -> None:
        target_engine = engine or self.engine
        section_column = ", section TEXT" if nullable_section else ""
        with target_engine.begin() as connection:
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

    def test_legacy_index_without_provenance_is_rejected(self) -> None:
        self.legacy_schema()
        self.initialize()
        with self.sessions() as db:
            with self.assertRaises(IndexCompatibilityError):
                require_compatible_index(db, "legacy.pdf")

    def test_search_rejects_mismatched_provenance_before_embedding(self) -> None:
        self.initialize()
        self.add_chunk("mismatched.pdf", vector(1.0))
        with self.sessions.begin() as db:
            metadata = db.get(DocumentIndex, "mismatched.pdf")
            assert metadata is not None
            metadata.embedding_model = "different-model"
        with patch.object(search, "SessionLocal", self.sessions), \
                patch.object(search, "embed_text") as embed:
            with self.assertRaises(IndexCompatibilityError):
                search.search_chunks("Synthetic question", document="mismatched.pdf")
            embed.assert_not_called()

    def test_selected_compatible_paper_is_not_blocked_by_other_profiles(self) -> None:
        self.initialize()
        good = self.add_chunk("good.pdf", vector(1.0))
        self.add_chunk("other.pdf", vector(1.0))
        with self.sessions.begin() as db:
            record = db.get(DocumentIndex, "other.pdf")
            assert record is not None
            record.embedding_dimensions = 1024
        with patch.object(search, "SessionLocal", self.sessions), \
                patch.object(search, "embed_text", return_value=vector(1.0)) as embed:
            self.assertEqual([c.id for c in search.search_chunks("Question", document="good.pdf")], [good])
            embed.reset_mock()
            for document in (None, "other.pdf"):
                with self.subTest(document=document), self.assertRaises(IndexCompatibilityError):
                    search.search_chunks("Question", document=document)
                embed.assert_not_called()

    def test_profile_change_during_embedding_is_rechecked_before_ranking(self) -> None:
        self.initialize()
        self.add_chunk("changing.pdf", vector(1.0))

        def embed_after_replacement(_: str) -> list[float]:
            # A real second write transaction can commit while inference runs.
            with self.sessions.begin() as db:
                db.execute(text("SET LOCAL lock_timeout = '2s'"))
                lock_index(db)
                record = db.get(DocumentIndex, "changing.pdf")
                assert record is not None
                record.embedding_model = "changed-profile"
            return vector(1.0)

        with patch.object(search, "SessionLocal", self.sessions), \
                patch.object(search, "embed_text", side_effect=embed_after_replacement) as embed:
            with self.assertRaises(IndexCompatibilityError):
                search.search_chunks("Question", document="changing.pdf")
            embed.assert_called_once()

    def test_unique_chunk_location_is_enforced_after_fresh_and_legacy_migrations(self) -> None:
        self.initialize()
        self.add_chunk("fresh-unique.pdf", vector(1.0))
        with self.assertRaises(IntegrityError), self.sessions.begin() as db:
            db.add(Chunk(document="fresh-unique.pdf", page=1, chunk_index=0,
                         text="Duplicate location", section="results", embedding=vector(1.0)))

        legacy_name = f"legacy_contract_{uuid4().hex}"
        with self.control.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{legacy_name}" TEMPLATE template0'))
        legacy_engine = create_engine(self.control.url.set(database=legacy_name))
        self.addCleanup(self.drop_database, legacy_name)
        self.addCleanup(legacy_engine.dispose)
        self.legacy_schema(engine=legacy_engine)
        with patch.object(init_db, "engine", legacy_engine):
            init_db.initialize_database()
        with self.assertRaises(DBAPIError), legacy_engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO chunks (document, page, chunk_index, text, embedding) "
                "VALUES ('legacy.pdf', 3, 0, 'Duplicate', CAST(:vector AS vector))"
            ), {"vector": json.dumps(vector(1.0))})

    def test_duplicate_legacy_locations_abort_migration_and_preserve_rows(self) -> None:
        self.legacy_schema()
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO chunks (document, page, chunk_index, text, embedding) "
                "SELECT document, page, chunk_index, text, embedding FROM chunks"
            ))
        with self.assertRaisesRegex(ValueError, "Duplicate chunk locations"):
            self.initialize()
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM chunks")), 2)
            self.assertEqual(list(connection.scalars(text(
                "SELECT id FROM chunks ORDER BY id"
            ))), [1, 2])
        # The documented recovery must work even on the oldest schema, whose
        # section column did not exist before this failed initialization.
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "legacy.pdf"
            paper.write_bytes(b"synthetic PDF")
            pages: list[PageData] = [{"document": paper.name, "page": 1, "text": "Replacement text."}]
            with patch.object(indexing, "SessionLocal", self.sessions), \
                    patch.object(indexing, "extract_pages", return_value=pages), \
                    patch.object(indexing, "embed_text", return_value=vector(1.0)):
                self.assertEqual(indexing.index_pdf(str(paper)), 1)
        self.initialize()
        with self.sessions() as db:
            self.assertEqual(list(db.scalars(select(Chunk.text))), ["Replacement text."])
            require_compatible_index(db, "legacy.pdf")

    def run_concurrent_mutation_pair(
        self, second_operation: Literal["replace", "remove"],
    ) -> None:
        """Hold an index transaction while a second production mutation waits."""
        self.initialize()
        self.add_chunk("shared.pdf", vector(1.0))
        first_locked = threading.Event()
        release_first = threading.Event()
        second_attempting = threading.Event()
        second_locked = threading.Event()
        errors: list[BaseException] = []
        real_lock = lock_index

        def coordinated_lock(db: Session) -> None:
            name = threading.current_thread().name
            if name == "replacement":
                real_lock(db)
                first_locked.set()
                if not release_first.wait(5):
                    raise TimeoutError("test did not release the replacement lock")
            elif name == "second-mutation":
                second_attempting.set()
                real_lock(db)
                second_locked.set()
            else:
                real_lock(db)

        def capture(callable_: Callable[[], object]) -> None:
            try:
                callable_()
            except BaseException as error:
                errors.append(error)

        with TemporaryDirectory() as temp:
            first_path = Path(temp) / "first" / "shared.pdf"
            first_path.parent.mkdir()
            first_path.write_bytes(b"first synthetic PDF")
            second_path = Path(temp) / "second" / "shared.pdf"
            second_path.parent.mkdir()
            second_path.write_bytes(b"second synthetic PDF")
            second_checksum = hashlib.sha256(second_path.read_bytes()).hexdigest()

            def extract(path: str, **kwargs: object) -> list[PageData]:
                return [{"document": Path(path).name, "page": 1,
                         "text": f"Synthetic {Path(path).parent.name} replacement."}]

            with patch.object(indexing, "SessionLocal", self.sessions), \
                    patch.object(indexing, "extract_pages", side_effect=extract), \
                    patch.object(indexing, "embed_text", return_value=vector(1.0)), \
                    patch.object(indexing, "lock_index", side_effect=coordinated_lock), \
                    patch("app.library.SessionLocal", self.sessions), \
                    patch("app.library.lock_index", side_effect=coordinated_lock):
                first = threading.Thread(
                    name="replacement", target=lambda: capture(
                        lambda: indexing.index_pdf(str(first_path))),
                )
                first.start()
                self.assertTrue(first_locked.wait(5), "first replacement did not acquire lock")

                if second_operation == "replace":
                    operation = lambda: indexing.index_pdf(str(second_path))
                else:
                    operation = lambda: remove_document("shared.pdf")
                second = threading.Thread(
                    name="second-mutation", target=lambda: capture(operation),
                )
                second.start()
                try:
                    self.assertTrue(second_attempting.wait(5), "second mutation did not reach lock")
                    self.assertFalse(second_locked.wait(0.1), "second mutation crossed held lock")
                finally:
                    release_first.set()
                    first.join(5)
                    second.join(5)
                self.assertFalse(first.is_alive(), "first mutation exceeded timeout")
                self.assertFalse(second.is_alive(), "second mutation exceeded timeout")
                self.assertTrue(second_locked.is_set(), "second mutation never acquired released lock")
                self.assertEqual(errors, [])

        with self.sessions() as db:
            chunks = list(db.scalars(select(Chunk).where(Chunk.document == "shared.pdf")))
            if second_operation == "replace":
                self.assertEqual([chunk.text for chunk in chunks], ["Synthetic second replacement."])
                metadata = db.get(DocumentIndex, "shared.pdf")
                assert metadata is not None
                self.assertEqual(metadata.pdf_sha256, second_checksum)
            else:
                self.assertEqual(chunks, [])
                self.assertIsNone(db.get(DocumentIndex, "shared.pdf"))

    def test_same_document_replacements_serialize(self) -> None:
        self.run_concurrent_mutation_pair("replace")

    def test_replacement_and_removal_serialize(self) -> None:
        self.run_concurrent_mutation_pair("remove")

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
