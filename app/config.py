"""Process-level settings; set environment variables before starting Python."""

import os
from typing import Literal, cast


def setting(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


GENERATOR_MODEL = setting("RAG_GENERATOR_MODEL", "qwen3:8b")
GROUNDING_MODEL = setting("RAG_GROUNDING_MODEL", "gpt-oss:20b")
JUDGE_MODEL = setting("RAG_JUDGE_MODEL", "qwen3:8b")
DATABASE_URL = setting("RAG_DATABASE_URL", "postgresql+psycopg://rag:rag@localhost:5432/rag")


def reasoning_setting(name: str, default: str) -> bool | Literal["low", "medium", "high"]:
    value = setting(name, default).lower()
    if value in {"true", "false"}:
        return value == "true"
    if value in {"low", "medium", "high"}:
        return cast(Literal["low", "medium", "high"], value)
    raise ValueError(f"{name} must be true, false, low, medium, or high")


DRAFT_THINK = reasoning_setting("RAG_DRAFT_THINK", "low")
VERIFIER_THINK = reasoning_setting("RAG_VERIFIER_THINK", "medium")
