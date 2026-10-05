"""Extract, embed and atomically replace one PDF in the paper index."""

from collections.abc import Callable
import hashlib
from pathlib import Path

import pymupdf
import httpx

from sqlalchemy import delete

from app.db.database import SessionLocal
from app.db.index_contract import embedding_profile, lock_index
from app.db.models import Chunk, DocumentIndex
from app.embeddings import MAX_EMBEDDING_BATCH_SIZE, embed_texts
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages


PDF_PATH = "data/sample.pdf"

CHUNK_SIZE = 500
OVERLAP = 100
MAX_PDF_PAGES = 500
MAX_PAGE_CHARS = 100_000
MAX_PDF_CHARS = 2_000_000
MAX_CHUNKS = 10_000
EXTRACTION_VERSION = f"pymupdf-text-v1:{pymupdf.VersionBind}"
CHUNKING_VERSION = "section-sentence-v1"


def pdf_checksum(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def index_pdf(pdf_path: str = PDF_PATH, *, progress: Callable[[str], None] | None = None) -> int:
    """Replace a document's chunks atomically, using its filename as identity."""
    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    path = Path(pdf_path)
    checksum = pdf_checksum(path)
    model, dimensions = embedding_profile()
    chunk_size, overlap = CHUNK_SIZE, OVERLAP
    report(f"Reading {path.name}…")
    pages = extract_pages(
        pdf_path,
        max_pages=MAX_PDF_PAGES,
        max_page_chars=MAX_PAGE_CHARS,
        max_total_chars=MAX_PDF_CHARS,
    )
    if pdf_checksum(path) != checksum:
        raise ValueError("PDF changed during extraction; the existing index was not replaced.")
    report(f"Read {len(pages)} PDF pages. Preparing chunks…")
    chunks = chunk_pages(
        pages,
        chunk_size=chunk_size,
        overlap=overlap,
        max_chunks=MAX_CHUNKS,
    )

    # Finish extraction and embedding before touching the existing index.
    db_chunks: list[Chunk] = []
    report(f"Embedding chunks: 0/{len(chunks)}")
    # Keep terminal output bounded even for large PDFs.
    report_every = max(1, (len(chunks) + 9) // 10)
    next_report = report_every
    if chunks:
        # One owned connection pool for this indexing operation; never a global
        # client or a write transaction held open during inference.
        with httpx.Client() as client:
            for start in range(0, len(chunks), MAX_EMBEDDING_BATCH_SIZE):
                batch = chunks[start:start + MAX_EMBEDDING_BATCH_SIZE]
                vectors = embed_texts([chunk["text"] for chunk in batch], client=client)
                for chunk, embedding in zip(batch, vectors, strict=True):
                    db_chunks.append(Chunk(
                        document=chunk["document"],
                        page=chunk["page"],
                        chunk_index=chunk["chunk_index"],
                        text=chunk["text"],
                        section=chunk.get("section", "unknown"),
                        embedding=embedding,
                    ))
                completed = start + len(batch)
                if completed >= next_report or completed == len(chunks):
                    report(f"Embedding chunks: {completed}/{len(chunks)}")
                    next_report = completed + report_every

    report("Saving index…")
    if pdf_checksum(path) != checksum or embedding_profile() != (model, dimensions):
        raise ValueError("PDF or embedding profile changed during indexing; the existing index was not replaced.")
    with SessionLocal.begin() as db:
        lock_index(db)
        db.execute(delete(Chunk).where(Chunk.document == path.name))
        db.execute(delete(DocumentIndex).where(DocumentIndex.document == path.name))
        db.add_all(db_chunks)
        if db_chunks:
            db.add(DocumentIndex(
                document=path.name, pdf_sha256=checksum,
                embedding_model=model, embedding_dimensions=dimensions,
                extraction_version=EXTRACTION_VERSION, chunking_version=CHUNKING_VERSION,
                chunk_size=chunk_size, overlap=overlap,
            ))

    return len(db_chunks)
