import math

import httpx

from app.config import SETTINGS
from app.llm.errors import OllamaResponseError, response_object
from app.llm.telemetry import observe_call, record_metadata


OLLAMA_EMBED_URL = SETTINGS.ollama_embed_url
EMBEDDING_MODEL = SETTINGS.embedding_model
# The persisted pgvector column in app.db.models has this fixed dimension.
EMBEDDING_DIMENSIONS = SETTINGS.embedding_dimensions
MAX_EMBEDDING_BATCH_SIZE = 16


def embed_text(text: str) -> list[float]:
    """Embed one question, retaining the existing single-text request contract."""
    return _embed(text, 1)[0]


def embed_texts(texts: list[str], *, client: httpx.Client | None = None) -> list[list[float]]:
    """Embed a bounded batch in input order; reject the whole invalid response."""
    if len(texts) > MAX_EMBEDDING_BATCH_SIZE:
        raise ValueError(f"An embedding batch must contain at most {MAX_EMBEDDING_BATCH_SIZE} texts")
    if not texts:
        return []
    return _embed(texts, len(texts), client=client)


def _embed(
    inputs: str | list[str], count: int, *, client: httpx.Client | None = None,
) -> list[list[float]]:
    with observe_call("embedding", EMBEDDING_MODEL) as call:
        post = httpx.post if client is None else client.post
        response = post(
            OLLAMA_EMBED_URL,
            json={
                "model": EMBEDDING_MODEL,
                "input": inputs,
            },
            timeout=120.0,
        )

        response.raise_for_status()

        data = response_object(response, "embedding")
        if call is not None:
            record_metadata(call, data)
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != count:
            raise OllamaResponseError("embedding")
        return [_validated_vector(vector) for vector in embeddings]


def _validated_vector(vector: object) -> list[float]:
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
