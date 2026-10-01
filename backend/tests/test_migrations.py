from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers the tables)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migrations_match_the_models(tmp_path: Path):
    """Fails if a model was changed without generating a migration for it."""
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(alembic_config(database_url), "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection), SQLModel.metadata
        )
    engine.dispose()

    assert differences == []


def test_migrations_can_be_undone(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    table_names = inspect(engine).get_table_names()
    engine.dispose()

    assert table_names == ["alembic_version"]
