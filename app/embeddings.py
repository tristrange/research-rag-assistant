from typing import TypedDict, cast

import httpx


class EmbeddingResponse(TypedDict):
    embeddings: list[list[float]]


OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"


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

    data = cast(EmbeddingResponse, response.json())
    return data["embeddings"][0]
