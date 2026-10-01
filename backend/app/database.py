from collections.abc import Iterator

from sqlmodel import Session, create_engine

from app.config import DATABASE_URL

# Tables are created and changed by Alembic migrations (see migrations/).
engine = create_engine(DATABASE_URL)


def get_session() -> Iterator[Session]:
    """Give each request its own database session (used by API endpoints later)."""
    with Session(engine) as session:
        yield session
