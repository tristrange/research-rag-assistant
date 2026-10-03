"""The stored vector profile and transaction boundary shared by index users."""

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app import embeddings
from app.db.models import Chunk, DocumentIndex


class IndexCompatibilityError(RuntimeError):
    """The selected corpus has unknown or incompatible embedding provenance."""


def embedding_profile() -> tuple[str, int]:
    return embeddings.EMBEDDING_MODEL, embeddings.EMBEDDING_DIMENSIONS


def lock_index(db: Session, *, shared: bool = False) -> None:
    """Serialize short mutations against one another and profile-checked reads.

    PostgreSQL releases this advisory lock on commit/rollback. SQLite is used
    only for unit tests; its existing single-writer transactions still apply.
    All application mutations must acquire this lock before reading/writing.
    """
    if db.get_bind().dialect.name == "postgresql":
        function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
        db.execute(text(f"SELECT {function}(731904, 1)"))


def require_compatible_index(db: Session, document: str | None = None) -> None:
    """Refuse unknown/mismatched vectors before sending a question to Ollama."""
    model, dimensions = embedding_profile()
    statement = select(Chunk.id).outerjoin(
        DocumentIndex, DocumentIndex.document == Chunk.document,
    ).where(or_(
        DocumentIndex.document.is_(None),
        DocumentIndex.embedding_model != model,
        DocumentIndex.embedding_dimensions != dimensions,
    ))
    if document is not None:
        statement = statement.where(Chunk.document == document)
    if db.scalar(statement.limit(1)) is not None:
        raise IndexCompatibilityError(
            "The selected index has unknown or incompatible embedding provenance. "
            "Run uv run python -m scripts.init_db, then reindex the selected papers "
            "with uv run python -m scripts.index_pdf <PDF path>."
        )
