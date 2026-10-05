import math

import httpx

from app.config import SETTINGS
from app.llm.errors import OllamaResponseError, response_object
from app.llm.telemetry import observe_call, record_metadata


OLLAMA_EMBED_URL = SETTINGS.ollama_embed_url
EMBEDDING_MODEL = SETTINGS.embedding_model
# The persisted pgvector column in app.db.models has this fixed dimension.
EMBEDDING_DIMENSIONS = SETTINGS.embedding_dimensions


def embed_text(text: str) -> list[float]:
    with observe_call("embedding", EMBEDDING_MODEL) as call:
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
        if call is not None:
            record_metadata(call, data)
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
