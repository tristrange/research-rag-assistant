from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import embed_text
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages


PDF_PATH = "data/sample.pdf"

CHUNK_SIZE = 500
OVERLAP = 100


def main():
    pages = extract_pages(PDF_PATH)
    chunks = chunk_pages(
        pages,
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
    )

    db = SessionLocal()

    try:
        for chunk in chunks:
            embedding = embed_text(chunk["text"])

            db_chunk = Chunk(
                document=chunk["document"],
                page=chunk["page"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                embedding=embedding,
            )

            db.add(db_chunk)

        db.commit()
        print(f"Indexed {len(chunks)} chunks")

    finally:
        db.close()


if __name__ == "__main__":
    main()
    
