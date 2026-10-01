"""Command-line tool for downloading spot prices. Run from the backend folder:

    uv run python -m app.fetch_prices --check     # test the API key (uses no quota)
    uv run python -m app.fetch_prices             # fill in any missing days up to today
    uv run python -m app.fetch_prices --start 2026-01-01 --end 2026-03-31
"""

import argparse
import datetime
import sys

from sqlmodel import Session

from app.config import METALS_API_KEY
from app.database import engine
from app.price_fetcher import (
    PriceFetchError,
    check_usage,
    make_client,
    missing_range,
    update_prices,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download daily metal spot prices.")
    parser.add_argument("--check", action="store_true", help="only test the API key")
    parser.add_argument("--start", type=datetime.date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--end", type=datetime.date.fromisoformat, help="YYYY-MM-DD")
    args = parser.parse_args()

    try:
        with make_client(METALS_API_KEY) as client:
            if args.check:
                usage = check_usage(client)
                print(
                    f"API key works. Plan: {usage['plan']}. "
                    f"Requests this month: {usage['used']} used, {usage['remaining']} remaining."
                )
                return 0

            with Session(engine) as session:
                today = datetime.date.today()
                if args.start:
                    start, end = args.start, args.end or today
                else:
                    needed = missing_range(session, today)
                    if needed is None:
                        print("Prices are already up to date.")
                        return 0
                    start, end = needed

                print(f"Downloading prices from {start} to {end}...")
                saved = update_prices(session, client, start, end)
                print(f"Saved {saved} prices.")
                return 0
    except PriceFetchError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
