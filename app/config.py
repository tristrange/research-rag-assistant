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


def model_family(model: str) -> str:
    return model.rsplit("/", 1)[-1].split(":", 1)[0].lower()


def qwen_family(model: str) -> str | None:
    family = model_family(model)
    return family if family in {"qwen3", "qwen3.5"} else None


DRAFT_THINK = reasoning_setting("RAG_DRAFT_THINK", "true" if qwen_family(GROUNDING_MODEL) else "low")
VERIFIER_THINK = reasoning_setting("RAG_VERIFIER_THINK", "true" if qwen_family(GROUNDING_MODEL) else "medium")
if qwen_family(GROUNDING_MODEL) and (not isinstance(DRAFT_THINK, bool) or not isinstance(VERIFIER_THINK, bool)):
    raise ValueError("Qwen grounding requires true or false for RAG_DRAFT_THINK and RAG_VERIFIER_THINK")


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


def resolve_grounding_sampling(
    model: str, draft_think: bool | str, verifier_think: bool | str,
    overrides: GroundingSampling,
) -> GroundingSampling:
    """Select the model family's profile, then overlay explicit sampling values."""
    defaults: dict[str, float | int] = {"temperature": 0.0}
    family = qwen_family(model)
    if model_family(model) == "gpt-oss":
        defaults.update(temperature=1.0, top_p=1.0)
    elif family and (draft_think is True or verifier_think is True):
        defaults.update(temperature=0.6 if family == "qwen3" else 1.0,
                        top_p=0.95, top_k=20, min_p=0.0,
                        presence_penalty=0.0 if family == "qwen3" else 1.5, repeat_penalty=1.0)
    # Only explicitly supplied values override the selected profile. In particular,
    # {} or a filter-only override must not reintroduce temperature zero for thinking.
    explicit = overrides.model_dump(exclude_unset=True, exclude_none=True)
    return GroundingSampling.model_validate(defaults | explicit)


GROUNDING_SAMPLING = resolve_grounding_sampling(
    GROUNDING_MODEL, DRAFT_THINK, VERIFIER_THINK,
    GroundingSampling.model_validate_json(setting("RAG_GROUNDING_SAMPLING", "{}")),
)


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
