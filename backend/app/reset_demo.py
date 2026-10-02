"""Reset the public demo: delete every purchase and add the sample ones again.

Runs every night on the demo database (see .github/workflows/update-demo-data.yml),
after that day's market data has been downloaded. Run from the backend folder:

    uv run python -m app.reset_demo

Because it deletes all purchases, it refuses to run unless DEMO_MODE is set, so
it can't wipe a real portfolio by mistake. It makes no API requests.
"""

import datetime
import sys

from sqlmodel import Session, delete

from app import config
from app.database import engine
from app.models import Purchase
from app.seed_demo import SeedError, add_demo_purchases


class ResetRefused(Exception):
    """The reset was refused because this isn't a demo database."""


def reset_demo(session: Session, today: datetime.date) -> list[Purchase]:
    """Replace all purchases with the sample ones, dated relative to today."""
    if config.DEMO_MODE == "off":
        raise ResetRefused(
            "DEMO_MODE isn't set, so this may be a real portfolio; nothing was deleted."
        )
    session.exec(delete(Purchase))
    return add_demo_purchases(session, today)  # commits the delete and the new rows together


def main() -> int:
    try:
        with Session(engine) as session:
            purchases = reset_demo(session, datetime.date.today())
    except (ResetRefused, SeedError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Demo reset: {len(purchases)} sample purchases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
