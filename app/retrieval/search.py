from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import embed_text


def list_documents() -> list[str]:
    """Return the exact filenames available for document-scoped queries."""
    db = SessionLocal()
    try:
        statement = select(Chunk.document).distinct().order_by(Chunk.document)
        return list(db.scalars(statement))
    finally:
        db.close()


def search_chunks(query: str, limit: int = 5, *, document: str | None = None) -> list[Chunk]:
    db = SessionLocal()

    try:
        if document is not None:
            indexed = db.scalar(
                select(Chunk.id).where(Chunk.document == document).limit(1)
            )
            if indexed is None:
                return []

        query_embedding = embed_text(query)
        statement = select(Chunk)
        if document is not None:
            statement = statement.where(Chunk.document == document)
        statement = statement.order_by(
            Chunk.embedding.cosine_distance(query_embedding), Chunk.id,
        ).limit(limit)

        return list(db.scalars(statement))

    finally:
        db.close()
