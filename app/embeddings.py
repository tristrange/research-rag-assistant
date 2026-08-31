import httpx


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

    data = response.json()
    return data["embeddings"][0]
