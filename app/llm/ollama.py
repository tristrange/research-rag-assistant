import httpx


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"


def generate(prompt: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
        },
        timeout=120.0,
    )

    response.raise_for_status()

    data = response.json()
    return data["message"]["content"]
