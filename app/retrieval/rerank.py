from sentence_transformers import CrossEncoder

from app.db.models import Chunk


MODEL_NAME = "BAAI/bge-reranker-base"

model = CrossEncoder(MODEL_NAME)


def rerank_chunks(
    query: str,
    chunks: list[Chunk],
    limit: int = 3,
) -> list[Chunk]:
    pairs = [
        (query, chunk.text)
        for chunk in chunks
    ]

    scores = model.predict(pairs)

    ranked = sorted(
        zip(chunks, scores),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        chunk
        for chunk, _ in ranked[:limit]
    ]
