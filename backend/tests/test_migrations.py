from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers the tables)
from tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def empty_database(tmp_path: Path) -> str:
    """TEST_DATABASE_URL if set (it must be empty), otherwise a new SQLite file."""
    return TEST_DATABASE_URL or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_migrations_match_the_models(tmp_path: Path):
    """Fails if a model was changed without generating a migration for it."""
    database_url = empty_database(tmp_path)
    config = alembic_config(database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection), SQLModel.metadata
        )
    engine.dispose()
    command.downgrade(config, "base")  # leave the database empty again

    assert differences == []


def test_migrations_can_be_undone_and_redone(tmp_path: Path):
    config = alembic_config(empty_database(tmp_path))

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")  # fails if undoing left anything behind
    command.downgrade(config, "base")

    engine = create_engine(empty_database(tmp_path))
    table_names = inspect(engine).get_table_names()
    engine.dispose()

    assert table_names == ["alembic_version"]
