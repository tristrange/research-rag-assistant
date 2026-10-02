from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
import math
import re
from time import perf_counter
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


Operation = Literal["chat", "embedding"]
CallStatus = Literal["complete", "failed"]
_NANOSECONDS_PER_MILLISECOND = 1_000_000
_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")


class ModelCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, validate_assignment=True)

    operation: Operation
    requested_model: str = Field(min_length=1)
    response_model: str | None = None
    elapsed_ms: float = Field(ge=0)
    status: CallStatus
    total_duration_ms: float | None = Field(default=None, ge=0)
    load_duration_ms: float | None = Field(default=None, ge=0)
    prompt_eval_duration_ms: float | None = Field(default=None, ge=0)
    eval_duration_ms: float | None = Field(default=None, ge=0)
    prompt_eval_count: int | None = Field(default=None, ge=0)
    eval_count: int | None = Field(default=None, ge=0)
    done_reason: str | None = None


class RuntimeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ollama_version: str | None = Field(default=None, min_length=1)
    model_digests: dict[str, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None]


_CAPTURED_CALLS: ContextVar[tuple[list[ModelCall], ...]] = ContextVar("model_call_capture", default=())


@contextmanager
def capture_calls() -> Iterator[list[ModelCall]]:
    """Capture calls here; nested calls also appear once in each active ancestor."""
    calls: list[ModelCall] = []
    token: Token[tuple[list[ModelCall], ...]] = _CAPTURED_CALLS.set((*_CAPTURED_CALLS.get(), calls))
    try:
        yield calls
    finally:
        _CAPTURED_CALLS.reset(token)


@contextmanager
def observe_call(operation: Operation, model: str) -> Iterator[ModelCall | None]:
    """Measure one provider operation only when a capture context is active."""
    call_buffers = _CAPTURED_CALLS.get()
    if not call_buffers:
        yield None
        return

    started = perf_counter()
    record = ModelCall(
        operation=operation,
        requested_model=model,
        elapsed_ms=0.0,
        status="complete",
    )
    try:
        yield record
    except BaseException:
        record.status = "failed"
        raise
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        record.elapsed_ms = elapsed_ms if math.isfinite(elapsed_ms) and elapsed_ms >= 0 else 0.0
        for calls in call_buffers:
            calls.append(record)


def _duration_ms(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    try:
        converted = value / _NANOSECONDS_PER_MILLISECOND
    except OverflowError:
        return None
    if not math.isfinite(converted) or converted < 0:
        return None
    return float(converted)


def _count(value: object) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def record_metadata(record: ModelCall, data: Mapping[str, object]) -> None:
    """Copy only recognized, well-typed Ollama metadata into the safe record."""
    response_model = data.get("model")
    if isinstance(response_model, str) and response_model:
        record.response_model = response_model

    done_reason = data.get("done_reason")
    if isinstance(done_reason, str):
        record.done_reason = done_reason

    for source, target in (
        ("total_duration", "total_duration_ms"),
        ("load_duration", "load_duration_ms"),
        ("prompt_eval_duration", "prompt_eval_duration_ms"),
        ("eval_duration", "eval_duration_ms"),
    ):
        converted = _duration_ms(data.get(source))
        if converted is not None:
            setattr(record, target, converted)

    for source, target in (
        ("prompt_eval_count", "prompt_eval_count"),
        ("eval_count", "eval_count"),
    ):
        converted_count = _count(data.get(source))
        if converted_count is not None:
            setattr(record, target, converted_count)


def _model_tag(model: str) -> str:
    final_component = model.rsplit("/", 1)[-1]
    return model if ":" in final_component else f"{model}:latest"


def _get_json(url: str) -> object | None:
    try:
        response = httpx.get(url, timeout=2.0)
        response.raise_for_status()
        data: object = response.json()
        return data
    except (httpx.HTTPError, ValueError):
        return None


def runtime_snapshot(models: list[str]) -> RuntimeSnapshot:
    """Read only version and model digests; failures leave those fields unknown."""
    from app.llm.ollama import OLLAMA_URL

    api_url = OLLAMA_URL.rsplit("/", 1)[0]
    version_data = _get_json(f"{api_url}/version")
    ollama_version: str | None = None
    if isinstance(version_data, dict):
        value = version_data.get("version")
        if isinstance(value, str) and value:
            ollama_version = value

    tags_data = _get_json(f"{api_url}/tags")
    digests_by_tag: dict[str, str | None] = {}
    if isinstance(tags_data, dict) and isinstance(tags_data.get("models"), list):
        for entry in tags_data["models"]:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            digest = entry.get("digest")
            if not isinstance(name, str) or not name:
                continue
            digests_by_tag[_model_tag(name)] = (
                digest.lower() if isinstance(digest, str) and _DIGEST.fullmatch(digest) else None
            )

    model_digests = {
        model: digests_by_tag.get(_model_tag(model))
        for model in models
    }
    return RuntimeSnapshot(ollama_version=ollama_version, model_digests=model_digests)
