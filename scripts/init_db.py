from sqlalchemy import Connection, text

from app.db.database import Base, engine
from app.db import models  # noqa: F401


def migrate_chunk_section(connection: Connection) -> None:
    """Add section metadata to an existing PostgreSQL index idempotently."""
    connection.execute(text(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section TEXT",
    ))
    connection.execute(text(
        "UPDATE chunks SET section = 'unknown' WHERE section IS NULL",
    ))
    connection.execute(text(
        "ALTER TABLE chunks ALTER COLUMN section SET DEFAULT 'unknown'",
    ))
    connection.execute(text(
        "ALTER TABLE chunks ALTER COLUMN section SET NOT NULL",
    ))


def initialize_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        migrate_chunk_section(connection)

    # Commit additive columns first: if duplicate detection fails, the indexer
    # must still be able to reindex the oldest schema to repair those locations.
    with engine.begin() as connection:
        migrate_chunk_locations(connection)


def migrate_chunk_locations(connection: Connection) -> None:
    """Never discard duplicate legacy chunks implicitly during migration."""
    duplicate = connection.scalar(text(
        "SELECT 1 FROM chunks GROUP BY document, page, chunk_index "
        "HAVING COUNT(*) > 1 LIMIT 1",
    ))
    if duplicate is not None:
        raise ValueError(
            "Duplicate chunk locations exist. Reindex the affected PDFs with "
            "scripts.index_pdf, then rerun scripts.init_db. Existing rows were preserved."
        )
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_location "
        "ON chunks (document, page, chunk_index)",
    ))


if __name__ == "__main__":
    try:
        initialize_database()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("Database initialized")
