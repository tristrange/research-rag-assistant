import json
from typing import TypedDict, cast

import httpx


class ChatMessage(TypedDict):
    content: str


class ChatResponse(TypedDict):
    message: ChatMessage


class ChatRequest(TypedDict, total=False):
    model: str
    messages: list[dict[str, str]]
    stream: bool
    format: dict[str, object]
    options: dict[str, float]
    think: bool


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
JUDGE_THINK = False


def chat(
    prompt: str,
    *,
    response_format: dict[str, object] | None = None,
    temperature: float | None = None,
    think: bool | None = None,
) -> str:
    payload = ChatRequest(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    if response_format is not None:
        payload["format"] = response_format
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    if think is not None:
        payload["think"] = think

    response = httpx.post(
        OLLAMA_URL,
        json=payload,
        timeout=120.0,
    )

    response.raise_for_status()

    data = cast(ChatResponse, response.json())
    return data["message"]["content"]


def generate(prompt: str) -> str:
    return chat(prompt)


def generate_json(
    prompt: str, schema: dict[str, object], *, think: bool = JUDGE_THINK,
) -> dict[str, object]:
    """Generate JSON constrained by an Ollama schema and parse it at runtime."""
    content = chat(prompt, response_format=schema, temperature=0.0, think=think)
    parsed: object = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama returned JSON that was not an object")
    return cast(dict[str, object], parsed)
