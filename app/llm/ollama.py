import json
from typing import Literal, TypedDict, cast

import httpx

from app.config import GENERATOR_MODEL, JUDGE_MODEL as JUDGE_MODEL
from app.llm.errors import OllamaResponseError, response_object
from app.llm.telemetry import observe_call, record_metadata


Thinking = bool | Literal["low", "medium", "high"]


class ChatRequest(TypedDict, total=False):
    model: str
    messages: list[dict[str, str]]
    stream: bool
    format: dict[str, object]
    options: dict[str, float | int]
    think: Thinking


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = GENERATOR_MODEL
JUDGE_THINK = False


class OllamaOutputLimitError(RuntimeError):
    """An incomplete model response is a failed call, not an evidence refusal."""


def default_timeout(think: Thinking | None) -> float:
    return 300.0 if think is True or isinstance(think, str) else 120.0


def chat(
    prompt: str,
    *,
    response_format: dict[str, object] | None = None,
    temperature: float | None = None,
    think: Thinking | None = None,
    model: str | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    sampling: dict[str, float | int] | None = None,
    timeout_seconds: float | None = None,
) -> str:
    payload = ChatRequest(
        model=model or MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    if response_format is not None:
        payload["format"] = response_format
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    if sampling is not None:
        payload.setdefault("options", {}).update(sampling)
    if num_ctx is not None:
        payload.setdefault("options", {})["num_ctx"] = num_ctx
    if num_predict is not None:
        payload.setdefault("options", {})["num_predict"] = num_predict
    if think is not None:
        payload["think"] = think

    requested_model = model or MODEL
    with observe_call("chat", requested_model) as call:
        response = httpx.post(
            OLLAMA_URL,
            json=payload,
            timeout=timeout_seconds if timeout_seconds is not None else default_timeout(think),
        )

        response.raise_for_status()

        data = response_object(response, "chat")
        if call is not None:
            record_metadata(call, data)
        if "done" in data and data["done"] is not True:
            raise OllamaResponseError("chat")
        if "done_reason" in data and not isinstance(data["done_reason"], str):
            raise OllamaResponseError("chat")
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaResponseError("chat")
        if data.get("done_reason") == "length":
            raise OllamaOutputLimitError("Ollama exhausted the output token budget before completing the response")
        # A string can still fail the grounding content schema; that is handled there.
        return cast(str, message["content"])


def generate(prompt: str) -> str:
    return chat(prompt)


def generate_json(
    prompt: str, schema: dict[str, object], *, think: Thinking = JUDGE_THINK,
    model: str | None = None,
    num_ctx: int | None = None, num_predict: int | None = None,
    sampling: dict[str, float | int] | None = None, timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Generate JSON constrained by an Ollama schema and parse it at runtime."""
    content = chat(prompt, response_format=schema, temperature=0.0, think=think,
                   num_ctx=num_ctx, num_predict=num_predict, model=model if model is not None else JUDGE_MODEL,
                   sampling=sampling, timeout_seconds=timeout_seconds)
    parsed: object = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama returned JSON that was not an object")
    return cast(dict[str, object], parsed)
