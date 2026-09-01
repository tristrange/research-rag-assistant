from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import embed_text


def search_chunks(query: str, limit: int = 5) -> list[Chunk]:
    query_embedding = embed_text(query)

    db = SessionLocal()

    try:
        statement = (
            select(Chunk)
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        return list(db.scalars(statement))

    finally:
        db.close()
