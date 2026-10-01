"""Command-line tool for downloading USD to CAD rates from the Bank of Canada.
Run from the backend folder:

    uv run python -m app.fetch_rates                          # fill in missing days up to today
    uv run python -m app.fetch_rates --start 2026-07-10       # from a date up to today
    uv run python -m app.fetch_rates --start 2026-07-10 --end 2026-08-31
"""

import argparse
import datetime
import sys

from sqlmodel import Session

from app.database import engine
from app.rate_fetcher import RateFetchError, make_client, missing_range, update_rates


def main() -> int:
    parser = argparse.ArgumentParser(description="Download daily USD to CAD exchange rates.")
    parser.add_argument("--start", type=datetime.date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--end", type=datetime.date.fromisoformat, help="YYYY-MM-DD")
    args = parser.parse_args()

    try:
        with make_client() as client, Session(engine) as session:
            today = datetime.date.today()
            if args.start:
                start, end = args.start, args.end or today
            else:
                needed = missing_range(session, today)
                if needed is None:
                    print("Exchange rates are already up to date.")
                    return 0
                start, end = needed

            print(f"Downloading USD to CAD rates from {start} to {end}...")
            saved = update_rates(session, client, start, end)
            print(f"Saved {saved} rates (business days only).")
            return 0
    except RateFetchError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
