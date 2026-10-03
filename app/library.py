"""Inventory and exact-filename removal of indexed papers."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, distinct, func, select

from app.db.database import SessionLocal
from app.db.index_contract import lock_index
from app.db.models import Chunk, DocumentIndex


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
    if not document.strip() or document in {".", ".."} or Path(document).name != document:
        raise ValueError("Use one exact indexed filename, not a path.")


def document_provenance(document: str) -> dict[str, str | int] | None:
    """Return recorded processing inputs, without reading the source PDF."""
    validate_document_name(document)
    with SessionLocal() as db:
        record = db.get(DocumentIndex, document)
        if record is None:
            return None
        return {
            "pdf_sha256": record.pdf_sha256,
            "embedding_model": record.embedding_model,
            "embedding_dimensions": record.embedding_dimensions,
            "extraction_version": record.extraction_version,
            "chunking_version": record.chunking_version,
            "chunk_size": record.chunk_size,
            "overlap": record.overlap,
        }


def remove_document(document: str) -> int:
    """Atomically remove matching chunks; never access or delete the source PDF."""
    validate_document_name(document)
    with SessionLocal.begin() as db:
        lock_index(db)
        removed = list(db.scalars(delete(Chunk).where(Chunk.document == document).returning(Chunk.id)))
        db.execute(delete(DocumentIndex).where(DocumentIndex.document == document))
    return len(removed)
