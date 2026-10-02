from typing import Literal

import httpx


Operation = Literal["chat", "embedding"]


class OllamaResponseError(RuntimeError):
    """An invalid provider envelope, distinct from rejected answer content."""

    def __init__(self, operation: Operation) -> None:
        self.operation = operation
        super().__init__(f"Ollama returned an invalid {operation} response. Check Ollama and retry.")


def response_object(response: httpx.Response, operation: Operation) -> dict[str, object]:
    """Decode a successful response without exposing its body in errors."""
    try:
        data: object = response.json()
    except ValueError:
        raise OllamaResponseError(operation) from None
    if not isinstance(data, dict):
        raise OllamaResponseError(operation)
    return data
