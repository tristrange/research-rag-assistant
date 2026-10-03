from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (Index("uq_chunks_location", "document", "page", "chunk_index", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(
        Text, nullable=False, default="unknown", server_default="unknown",
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(768))


class DocumentIndex(Base):
    """Provenance for a successfully saved document; absent for legacy indexes."""

    __tablename__ = "document_indexes"

    document: Mapped[str] = mapped_column(Text, primary_key=True)
    pdf_sha256: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(Text)
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    extraction_version: Mapped[str] = mapped_column(Text)
    chunking_version: Mapped[str] = mapped_column(Text)
    chunk_size: Mapped[int] = mapped_column(Integer)
    overlap: Mapped[int] = mapped_column(Integer)
