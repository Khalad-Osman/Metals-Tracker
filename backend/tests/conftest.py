import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  (registers the tables)
from app.database import get_session
from app.main import app


# Tests use a fresh in-memory SQLite database by default. To run them against
# another database (e.g. PostgreSQL), set TEST_DATABASE_URL to an EMPTY database
# used only for tests: every test creates the tables and drops them afterwards.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture
def session() -> Iterator[Session]:
    """A fresh, empty database for each test."""
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """An API client whose requests use the in-memory test database."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
