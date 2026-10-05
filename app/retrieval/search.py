from dataclasses import dataclass, field
from functools import cached_property

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.index_contract import IndexCompatibilityError, embedding_profile, lock_index, require_compatible_index
from app.db.models import Chunk
from app.embeddings import embed_text


@dataclass(frozen=True)
class QuestionEmbedding:
    """One lazy vector for one question in one request, never a global cache."""

    question: str = field(repr=False)
    profile: tuple[str, int] = field(default_factory=embedding_profile, init=False)

    def require_current_profile(self) -> None:
        if self.profile != embedding_profile():
            raise IndexCompatibilityError("The embedding profile changed during the request. Start a new request.")

    @cached_property
    def vector(self) -> tuple[float, ...]:
        self.require_current_profile()
        vector = tuple(embed_text(self.question))
        self.require_current_profile()
        return vector


def list_documents() -> list[str]:
    """Return the exact filenames available for document-scoped queries."""
    db = SessionLocal()
    try:
        statement = select(Chunk.document).distinct().order_by(Chunk.document)
        return list(db.scalars(statement))
    finally:
        db.close()


def search_chunks(
    query: str,
    limit: int = 5,
    *,
    document: str | None = None,
    sections: tuple[str, ...] | None = None,
    query_embedding: QuestionEmbedding | None = None,
) -> list[Chunk]:
    """Backward-compatible text entry point with optional request-owned reuse."""
    embedding = QuestionEmbedding(query) if query_embedding is None else query_embedding
    if embedding.question != query:
        raise ValueError("The embedding must belong to the requested question")
    return search_by_embedding(embedding, limit, document=document, sections=sections)


def search_by_embedding(
    embedding: QuestionEmbedding,
    limit: int = 5,
    *,
    document: str | None = None,
    sections: tuple[str, ...] | None = None,
) -> list[Chunk]:
    """Filter/rank with a lazy request vector and recheck every selected scope."""
    db = SessionLocal()

    try:
        lock_index(db, shared=True)
        require_compatible_index(db, document)
        embedding.require_current_profile()
        if document is not None:
            indexed = db.scalar(
                select(Chunk.id).where(Chunk.document == document).limit(1)
            )
            if indexed is None:
                return []

        # Release the read lock during inference; check again under lock before
        # ranking in case a writer committed a different profile meanwhile.
        db.rollback()
        query_vector = embedding.vector
        lock_index(db, shared=True)
        require_compatible_index(db, document)
        embedding.require_current_profile()
        statement = select(Chunk)
        if document is not None:
            statement = statement.where(Chunk.document == document)
        if sections is not None:
            statement = statement.where(Chunk.section.in_(sections))
        statement = statement.order_by(
            Chunk.embedding.cosine_distance(list(query_vector)), Chunk.id,
        ).limit(limit)

        return list(db.scalars(statement))

    finally:
        db.close()
