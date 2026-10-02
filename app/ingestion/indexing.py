"""Extract, embed and atomically replace one PDF in the paper index."""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import delete

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import embed_text
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages


PDF_PATH = "data/sample.pdf"

CHUNK_SIZE = 500
OVERLAP = 100
MAX_PDF_PAGES = 500
MAX_PAGE_CHARS = 100_000
MAX_PDF_CHARS = 2_000_000
MAX_CHUNKS = 10_000


def index_pdf(pdf_path: str = PDF_PATH, *, progress: Callable[[str], None] | None = None) -> int:
    """Replace a document's chunks atomically, using its filename as identity."""
    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    report(f"Reading {Path(pdf_path).name}…")
    pages = extract_pages(
        pdf_path,
        max_pages=MAX_PDF_PAGES,
        max_page_chars=MAX_PAGE_CHARS,
        max_total_chars=MAX_PDF_CHARS,
    )
    report(f"Read {len(pages)} PDF pages. Preparing chunks…")
    chunks = chunk_pages(
        pages,
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
        max_chunks=MAX_CHUNKS,
    )

    # Finish extraction and embedding before touching the existing index.
    db_chunks: list[Chunk] = []
    report(f"Embedding chunks: 0/{len(chunks)}")
    # Keep terminal output bounded even for large PDFs.
    report_every = max(1, (len(chunks) + 9) // 10)
    for completed, chunk in enumerate(chunks, start=1):
        db_chunks.append(Chunk(
            document=chunk["document"],
            page=chunk["page"],
            chunk_index=chunk["chunk_index"],
            text=chunk["text"],
            section=chunk.get("section", "unknown"),
            embedding=embed_text(chunk["text"]),
        ))
        if completed % report_every == 0 or completed == len(chunks):
            report(f"Embedding chunks: {completed}/{len(chunks)}")

    report("Saving index…")
    with SessionLocal.begin() as db:
        db.execute(delete(Chunk).where(Chunk.document == Path(pdf_path).name))
        db.add_all(db_chunks)

    return len(db_chunks)
