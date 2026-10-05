"""Resolve one immutable configuration snapshot when the process starts."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
import os
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictInt


type Thinking = bool | Literal["low", "medium", "high"]


def setting(name: str, default: str, environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    value = source.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def reasoning_setting(name: str, default: str, environ: Mapping[str, str] | None = None) -> Thinking:
    value = setting(name, default, environ).lower()
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


class GroundingSampling(BaseModel):
    """Explicit Ollama sampling overrides; omitted filters use model defaults."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, frozen=True)
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


def timeout_setting(environ: Mapping[str, str] | None = None) -> float | None:
    source = os.environ if environ is None else environ
    if "RAG_GROUNDING_TIMEOUT_SECONDS" not in source:
        return None
    value = float(setting("RAG_GROUNDING_TIMEOUT_SECONDS", "300", source))
    if not math.isfinite(value) or not 0 < value <= 600:
        raise ValueError("RAG_GROUNDING_TIMEOUT_SECONDS must be finite and between 0 (exclusive) and 600")
    return value


def default_timeout(think: Thinking | None) -> float:
    return 300.0 if think is True or isinstance(think, str) else 120.0


@dataclass(frozen=True)
class Settings:
    """Effective model/service settings; database credentials stay out of repr."""

    generator_model: str
    grounding_model: str
    judge_model: str
    database_url: str = field(repr=False)
    draft_think: Thinking
    verifier_think: Thinking
    grounding_sampling: GroundingSampling
    grounding_timeout_seconds: float | None
    grounding_output_tokens: int
    grounding_context_tokens: int = 12288
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    ollama_chat_url: str = "http://localhost:11434/api/chat"
    ollama_embed_url: str = "http://localhost:11434/api/embed"

    @property
    def grounding_draft_timeout_seconds(self) -> float:
        return self.grounding_timeout_seconds if self.grounding_timeout_seconds is not None else default_timeout(self.draft_think)

    @property
    def grounding_verifier_timeout_seconds(self) -> float:
        return self.grounding_timeout_seconds if self.grounding_timeout_seconds is not None else default_timeout(self.verifier_think)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Resolve profiles/overrides once, using only the supplied environment.

    Passing an empty mapping requests defaults, independent of the shell. This
    factory neither reads .env files nor mutates the process environment.
    """
    source = dict(os.environ if environ is None else environ)
    generator_model = setting("RAG_GENERATOR_MODEL", "qwen3:8b", source)
    grounding_model = setting("RAG_GROUNDING_MODEL", "gpt-oss:20b", source)
    judge_model = setting("RAG_JUDGE_MODEL", "qwen3:8b", source)
    database_url = setting("RAG_DATABASE_URL", "postgresql+psycopg://rag@localhost:5432/rag", source)
    draft_think = reasoning_setting("RAG_DRAFT_THINK", "true" if qwen_family(grounding_model) else "low", source)
    verifier_think = reasoning_setting("RAG_VERIFIER_THINK", "true" if qwen_family(grounding_model) else "medium", source)
    if qwen_family(grounding_model) and (not isinstance(draft_think, bool) or not isinstance(verifier_think, bool)):
        raise ValueError("Qwen grounding requires true or false for RAG_DRAFT_THINK and RAG_VERIFIER_THINK")
    sampling = resolve_grounding_sampling(
        grounding_model, draft_think, verifier_think,
        GroundingSampling.model_validate_json(setting("RAG_GROUNDING_SAMPLING", "{}", source)),
    )
    timeout = timeout_setting(source)
    output_tokens = int(setting("RAG_GROUNDING_OUTPUT_TOKENS", "4096", source))
    if not 1 <= output_tokens <= 8192:
        raise ValueError("RAG_GROUNDING_OUTPUT_TOKENS must be between 1 and 8192")
    return Settings(
        generator_model=generator_model, grounding_model=grounding_model,
        judge_model=judge_model, database_url=database_url,
        draft_think=draft_think, verifier_think=verifier_think,
        grounding_sampling=sampling, grounding_timeout_seconds=timeout,
        grounding_output_tokens=output_tokens,
    )


SETTINGS = load_settings()

# Compatibility exports for existing evaluation imports. All values come from
# the same startup snapshot; no second environment/profile resolution occurs.
GENERATOR_MODEL = SETTINGS.generator_model
GROUNDING_MODEL = SETTINGS.grounding_model
JUDGE_MODEL = SETTINGS.judge_model
DATABASE_URL = SETTINGS.database_url
DRAFT_THINK = SETTINGS.draft_think
VERIFIER_THINK = SETTINGS.verifier_think
GROUNDING_SAMPLING = SETTINGS.grounding_sampling
GROUNDING_TIMEOUT_SECONDS = SETTINGS.grounding_timeout_seconds
GROUNDING_OUTPUT_TOKENS = SETTINGS.grounding_output_tokens
