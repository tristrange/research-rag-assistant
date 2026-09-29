"""Process-level settings; set environment variables before starting Python."""

import math
import os
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictInt


def setting(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


GENERATOR_MODEL = setting("RAG_GENERATOR_MODEL", "qwen3:8b")
GROUNDING_MODEL = setting("RAG_GROUNDING_MODEL", "gpt-oss:20b")
JUDGE_MODEL = setting("RAG_JUDGE_MODEL", "qwen3:8b")
DATABASE_URL = setting("RAG_DATABASE_URL", "postgresql+psycopg://rag@localhost:5432/rag")


def reasoning_setting(name: str, default: str) -> bool | Literal["low", "medium", "high"]:
    value = setting(name, default).lower()
    if value in {"true", "false"}:
        return value == "true"
    if value in {"low", "medium", "high"}:
        return cast(Literal["low", "medium", "high"], value)
    raise ValueError(f"{name} must be true, false, low, medium, or high")


DRAFT_THINK = reasoning_setting("RAG_DRAFT_THINK", "low")
VERIFIER_THINK = reasoning_setting("RAG_VERIFIER_THINK", "medium")


class GroundingSampling(BaseModel):
    """Explicit Ollama sampling overrides; omitted filters use model defaults."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    temperature: float = Field(default=0.0, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    top_k: StrictInt | None = Field(default=None, ge=1, le=1000)
    min_p: float | None = Field(default=None, ge=0, le=1)
    presence_penalty: float | None = Field(default=None, ge=0, le=2)
    repeat_penalty: float | None = Field(default=None, gt=0, le=2)

    def options(self) -> dict[str, float | int]:
        return cast(dict[str, float | int], self.model_dump(exclude_none=True))


GROUNDING_SAMPLING = GroundingSampling.model_validate_json(setting("RAG_GROUNDING_SAMPLING", "{}"))


def timeout_setting() -> float | None:
    if "RAG_GROUNDING_TIMEOUT_SECONDS" not in os.environ:
        return None
    value = float(setting("RAG_GROUNDING_TIMEOUT_SECONDS", "300"))
    if not math.isfinite(value) or not 0 < value <= 600:
        raise ValueError("RAG_GROUNDING_TIMEOUT_SECONDS must be finite and between 0 (exclusive) and 600")
    return value


GROUNDING_TIMEOUT_SECONDS = timeout_setting()
GROUNDING_OUTPUT_TOKENS = int(setting("RAG_GROUNDING_OUTPUT_TOKENS", "4096"))
if not 1 <= GROUNDING_OUTPUT_TOKENS <= 8192:
    raise ValueError("RAG_GROUNDING_OUTPUT_TOKENS must be between 1 and 8192")
