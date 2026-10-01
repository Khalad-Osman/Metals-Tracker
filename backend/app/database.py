import os
from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

# SQLite file in the backend folder for now; set DATABASE_URL to use PostgreSQL later.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./metals.db")

engine = create_engine(DATABASE_URL)


def create_db_and_tables() -> None:
    # Import models so SQLModel knows about their tables before creating them.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Give each request its own database session (used by API endpoints later)."""
    with Session(engine) as session:
        yield session
