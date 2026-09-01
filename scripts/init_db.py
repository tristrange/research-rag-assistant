from sqlalchemy import text

from app.db.database import Base, engine
from app.db import models  # noqa: F401


with engine.begin() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

Base.metadata.create_all(engine)

print("Database initialized")
