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


if __name__ == "__main__":
    initialize_database()
    print("Database initialized")
