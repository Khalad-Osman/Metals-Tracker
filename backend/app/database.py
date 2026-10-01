import os
from collections.abc import Iterator

from sqlmodel import Session, create_engine

# SQLite file in the backend folder for now; set DATABASE_URL to use PostgreSQL later.
# Tables are created and changed by Alembic migrations (see migrations/).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./metals.db")

engine = create_engine(DATABASE_URL)


def get_session() -> Iterator[Session]:
    """Give each request its own database session (used by API endpoints later)."""
    with Session(engine) as session:
        yield session
