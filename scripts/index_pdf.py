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


def index_pdf(pdf_path: str = PDF_PATH) -> int:
    """Replace a document's chunks atomically, using its filename as identity."""
    pages = extract_pages(pdf_path)
    chunks = chunk_pages(
        pages,
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
    )

    # Finish extraction and embedding before touching the existing index.
    db_chunks = [
        Chunk(
            document=chunk["document"],
            page=chunk["page"],
            chunk_index=chunk["chunk_index"],
            text=chunk["text"],
            embedding=embed_text(chunk["text"]),
        )
        for chunk in chunks
    ]

    with SessionLocal.begin() as db:
        db.execute(delete(Chunk).where(Chunk.document == Path(pdf_path).name))
        db.add_all(db_chunks)

    return len(db_chunks)


def main():
    print(f"Indexed {index_pdf()} chunks")


if __name__ == "__main__":
    main()
