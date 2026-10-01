"""Inventory and exact-filename removal of indexed papers."""

from dataclasses import dataclass

from sqlalchemy import delete, distinct, func, select

from app.db.database import SessionLocal
from app.db.models import Chunk


@dataclass(frozen=True)
class IndexedDocument:
    document: str
    chunks: int
    indexed_pages: int


def library_inventory() -> list[IndexedDocument]:
    """Count stored chunks and pages, without reading paper text or PDFs."""
    statement = select(
        Chunk.document, func.count(Chunk.id), func.count(distinct(Chunk.page)),
    ).group_by(Chunk.document).order_by(Chunk.document)
    with SessionLocal() as db:
        return [IndexedDocument(document, chunks, pages)
                for document, chunks, pages in db.execute(statement)]


def validate_document_name(document: str) -> None:
    if not document.strip() or document in {".", ".."} or "/" in document or "\\" in document:
        raise ValueError("Use one exact indexed filename, not a path.")


def remove_document(document: str) -> int:
    """Atomically remove matching chunks; never access or delete the source PDF."""
    validate_document_name(document)
    with SessionLocal.begin() as db:
        removed = list(db.scalars(delete(Chunk).where(Chunk.document == document).returning(Chunk.id)))
    return len(removed)
