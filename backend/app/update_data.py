"""Bring all market data up to date with one command. Run from the backend folder:

    uv run python -m app.update_data

Fills in any missing days of USD to CAD exchange rates (Bank of Canada) and
metal spot prices (metals.dev, about 1 of the 100 monthly requests per run).
If one source fails, the other is still updated. To fetch a specific date
range instead, use app.fetch_rates or app.fetch_prices with --start/--end.
"""

import datetime
import sys
from collections.abc import Callable

import httpx2
from sqlmodel import Session

from app import price_fetcher, rate_fetcher
from app.config import METALS_DEV_API_KEY
from app.database import engine


def update_all(
    session: Session,
    today: datetime.date,
    make_rate_client: Callable[[], httpx2.Client],
    make_price_client: Callable[[], httpx2.Client],
) -> tuple[list[str], bool]:
    """Update exchange rates, then spot prices.

    Returns a message for each step, and whether every step succeeded.
    """
    messages = []
    all_ok = True

    # Exchange rates first: free, no key, so they're the least likely to fail.
    try:
        needed = rate_fetcher.missing_range(session, today)
        if needed is None:
            messages.append("Exchange rates: already up to date.")
        else:
            start, end = needed
            with make_rate_client() as client:
                saved = rate_fetcher.update_rates(session, client, start, end)
            messages.append(f"Exchange rates: saved {saved} for {start} to {end}.")
    except rate_fetcher.RateFetchError as error:
        messages.append(f"Exchange rates: FAILED. {error}")
        all_ok = False

    try:
        needed = price_fetcher.missing_range(session, today)
        if needed is None:
            messages.append("Spot prices: already up to date.")
        else:
            start, end = needed
            requests = price_fetcher.requests_needed(start, end)
            with make_price_client() as client:
                saved = price_fetcher.update_prices(session, client, start, end)
            messages.append(
                f"Spot prices: saved {saved} for {start} to {end} ({requests} API request(s))."
            )
    except price_fetcher.PriceFetchError as error:
        messages.append(f"Spot prices: FAILED. {error}")
        all_ok = False

    return messages, all_ok


def main() -> int:
    with Session(engine) as session:
        messages, all_ok = update_all(
            session,
            datetime.date.today(),
            make_rate_client=rate_fetcher.make_client,
            make_price_client=lambda: price_fetcher.make_client(METALS_DEV_API_KEY),
        )
    for message in messages:
        print(message)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
