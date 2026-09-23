from functools import cache

from sentence_transformers import CrossEncoder

from app.db.models import Chunk


MODEL_NAME = "BAAI/bge-reranker-base"

@cache
def get_model() -> CrossEncoder:
    model: CrossEncoder = CrossEncoder(MODEL_NAME)
    return model


def rerank_chunks(
    query: str,
    chunks: list[Chunk],
    limit: int = 3,
) -> list[Chunk]:
    if not chunks:
        return []

    pairs = [
        (query, chunk.text)
        for chunk in chunks
    ]

    scores = get_model().predict(pairs)

    ranked = sorted(
        zip(chunks, scores),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        chunk
        for chunk, _ in ranked[:limit]
    ]


def with_vector_reserve(reranked: list[Chunk], vector_ranked: list[Chunk]) -> list[Chunk]:
    """Append the highest vector-ranked chunk absent from the reranked selection."""
    selected = {(chunk.document, chunk.page, chunk.chunk_index) for chunk in reranked}
    for chunk in vector_ranked:
        if (chunk.document, chunk.page, chunk.chunk_index) not in selected:
            return [*reranked, chunk]
    return reranked
