"""Read-only setup checks; no inference, indexing or model downloads."""

from typing import Literal

import httpx
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL, GROUNDING_MODEL
from app.db.models import Chunk
from app.embeddings import EMBEDDING_MODEL, OLLAMA_EMBED_URL


CHECK_TIMEOUT_SECONDS = 3
OLLAMA_TAGS_URL = OLLAMA_EMBED_URL.rsplit("/", 1)[0] + "/tags"


class ServiceCheck(BaseModel):
    name: Literal["database", "ollama", "answer_model", "embedding_model"]
    status: Literal["ok", "error", "unknown"]
    message: str


class ServiceStatus(BaseModel):
    available: bool
    checks: list[ServiceCheck]


def check_database() -> ServiceCheck:
    # Isolate probe timeouts from normal queries and avoid retaining a probe pool.
    probe = create_engine(DATABASE_URL, poolclass=NullPool, connect_args={
        "connect_timeout": CHECK_TIMEOUT_SECONDS,
        "options": f"-c statement_timeout={CHECK_TIMEOUT_SECONDS * 1000}",
    })
    try:
        with probe.connect() as connection:
            # LIMIT 0 checks every expected column without reading paper text.
            connection.execute(select(Chunk).limit(0))
        return ServiceCheck(name="database", status="ok", message="Database and paper-index schema are accessible.")
    except SQLAlchemyError:
        return ServiceCheck(name="database", status="error", message="Check PostgreSQL and your .env settings, then run uv run python -m scripts.init_db. Reload the page afterward to refresh the paper list.")
    finally:
        probe.dispose()


def model_tag(model: str) -> str:
    return model if ":" in model.rsplit("/", 1)[-1] else f"{model}:latest"


def check_ollama() -> list[ServiceCheck]:
    try:
        response = httpx.get(OLLAMA_TAGS_URL, timeout=CHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        data: object = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ValueError("invalid model list")
        names: set[str] = set()
        for entry in data["models"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ValueError("invalid model entry")
            names.add(model_tag(entry["name"]))
    except (httpx.HTTPError, ValueError):
        return [
            ServiceCheck(name="ollama", status="error", message="Could not read Ollama's model list. Open Ollama or run ollama serve, then check services again."),
            ServiceCheck(name="answer_model", status="unknown", message="Answer model not checked because Ollama's model list is unavailable."),
            ServiceCheck(name="embedding_model", status="unknown", message="Embedding model not checked because Ollama's model list is unavailable."),
        ]
    checks = [ServiceCheck(name="ollama", status="ok", message="Ollama's model list is accessible.")]
    models: list[tuple[Literal["answer_model", "embedding_model"], str]] = [
        ("answer_model", GROUNDING_MODEL), ("embedding_model", EMBEDDING_MODEL),
    ]
    for name, model in models:
        installed = model_tag(model) in names
        checks.append(ServiceCheck(
            name=name, status="ok" if installed else "error",
            message=f"{model} is installed." if installed else f"Install the missing model with ollama pull {model}.",
        ))
    return checks


def service_status() -> ServiceStatus:
    checks = [check_database(), *check_ollama()]
    return ServiceStatus(available=all(check.status == "ok" for check in checks), checks=checks)
