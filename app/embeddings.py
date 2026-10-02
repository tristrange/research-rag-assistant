import math

import httpx

from app.llm.errors import OllamaResponseError, response_object


OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"
# The persisted pgvector column in app.db.models has this fixed dimension.
EMBEDDING_DIMENSIONS = 768


def embed_text(text: str) -> list[float]:
    response = httpx.post(
        OLLAMA_EMBED_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": text,
        },
        timeout=120.0,
    )

    response.raise_for_status()

    data = response_object(response, "embedding")
    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != 1:
        raise OllamaResponseError("embedding")
    vector = embeddings[0]
    if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
        raise OllamaResponseError("embedding")
    result: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OllamaResponseError("embedding")
        try:
            number = float(value)
        except OverflowError:
            raise OllamaResponseError("embedding") from None
        if not math.isfinite(number):
            raise OllamaResponseError("embedding")
        result.append(number)
    return result
