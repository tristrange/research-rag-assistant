from sqlalchemy import delete

from app.db.database import SessionLocal
from app.db.models import Chunk
from app.embeddings import embed_text
from app.ingestion.chunking import chunk_pages
from app.ingestion.pdf import extract_pages
from app.retrieval.search import search_chunks
from scripts.retrieval_cases import TEST_CASES


PDF_PATH = "data/sample.pdf"

CONFIGURATIONS = [
    (500, 100),
    (1000, 200),
    (1500, 300),
]


def clear_chunks() -> None:
    db = SessionLocal()

    try:
        db.execute(delete(Chunk))
        db.commit()
    finally:
        db.close()


def index_pdf(chunk_size: int, overlap: int) -> int:
    pages = extract_pages(PDF_PATH)
    chunks = chunk_pages(
        pages,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    db = SessionLocal()

    try:
        for chunk in chunks:
            embedding = embed_text(chunk["text"])

            db.add(
                Chunk(
                    document=chunk["document"],
                    page=chunk["page"],
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    embedding=embedding,
                )
            )

        db.commit()
        return len(chunks)

    finally:
        db.close()


def first_relevant_rank(
    retrieved_pages: list[int],
    expected_pages: list[int],
) -> int | None:
    for rank, page in enumerate(retrieved_pages, start=1):
        if page in expected_pages:
            return rank

    return None


def evaluate() -> dict[str, float]:
    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_rank_sum = 0.0

    for test in TEST_CASES:
        results = search_chunks(test["question"], limit=5)
        retrieved_pages = [chunk.page for chunk in results]

        rank = first_relevant_rank(
            retrieved_pages,
            test["expected_pages"],
        )

        if rank is not None:
            reciprocal_rank_sum += 1 / rank

        if rank is not None and rank <= 1:
            hit_at_1 += 1

        if rank is not None and rank <= 3:
            hit_at_3 += 1

        if rank is not None and rank <= 5:
            hit_at_5 += 1

    total = len(TEST_CASES)

    return {
        "hit@1": hit_at_1 / total,
        "hit@3": hit_at_3 / total,
        "hit@5": hit_at_5 / total,
        "mrr": reciprocal_rank_sum / total,
    }


def main() -> None:
    print(
        f"{'Chunk':>8} "
        f"{'Overlap':>8} "
        f"{'Chunks':>8} "
        f"{'H@1':>8} "
        f"{'H@3':>8} "
        f"{'H@5':>8} "
        f"{'MRR':>8}"
    )

    for chunk_size, overlap in CONFIGURATIONS:
        clear_chunks()

        chunk_count = index_pdf(
            chunk_size=chunk_size,
            overlap=overlap,
        )

        metrics = evaluate()

        print(
            f"{chunk_size:>8} "
            f"{overlap:>8} "
            f"{chunk_count:>8} "
            f"{metrics['hit@1']:>8.2f} "
            f"{metrics['hit@3']:>8.2f} "
            f"{metrics['hit@5']:>8.2f} "
            f"{metrics['mrr']:>8.2f}"
        )


if __name__ == "__main__":
    main()
