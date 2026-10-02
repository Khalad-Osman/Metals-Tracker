"""Copy all data from one database into another, e.g. from SQLite into PostgreSQL.

Run from the backend folder, after creating the tables in the target database
with `uv run alembic upgrade head`:

    uv run python -m app.copy_database --source sqlite:///metals.db

The target is DATABASE_URL (from backend/.env). It must be empty: the copy
refuses to run if the target already has any purchases, prices or rates.
"""

import argparse
import sys

from sqlalchemy import Engine, text
from sqlmodel import Session, SQLModel, create_engine, func, select

from app.config import DATABASE_URL
from app.models import ExchangeRate, MetalPrice, Purchase

TABLES: list[type[SQLModel]] = [Purchase, MetalPrice, ExchangeRate]


class CopyError(Exception):
    """The copy can't be done safely."""


def count_rows(session: Session, table: type[SQLModel]) -> int:
    return session.exec(select(func.count()).select_from(table)).one()


def copy_database(source: Engine, target: Engine) -> dict[str, int]:
    """Copy every row (keeping its id) from source to target. Returns rows copied per table."""
    copied = {}
    with Session(source) as source_session, Session(target) as target_session:
        for table in TABLES:
            if count_rows(target_session, table) > 0:
                raise CopyError(
                    f"The target already has {table.__tablename__} rows; "
                    "it must be empty so nothing is duplicated or overwritten."
                )

        for table in TABLES:
            rows = source_session.exec(select(table)).all()
            for row in rows:
                target_session.add(table.model_validate(row.model_dump()))
            copied[table.__tablename__] = len(rows)
        target_session.commit()

        if target.dialect.name == "postgresql":
            # Rows were inserted with their original ids, so PostgreSQL's id counters
            # didn't move. Point each counter past the highest id, or the next new
            # row would be given an id that's already taken.
            for table in TABLES:
                name = table.__tablename__
                target_session.exec(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {name}), 0) + 1, false)"
                    )
                )
            target_session.commit()

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy all data into DATABASE_URL.")
    parser.add_argument("--source", required=True, help="e.g. sqlite:///metals.db")
    args = parser.parse_args()

    if args.source == DATABASE_URL:
        print("Error: the source and target are the same database.", file=sys.stderr)
        return 1

    source, target = create_engine(args.source), create_engine(DATABASE_URL)
    try:
        copied = copy_database(source, target)
    except CopyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        source.dispose()
        target.dispose()

    for table, count in copied.items():
        print(f"Copied {count} {table} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
