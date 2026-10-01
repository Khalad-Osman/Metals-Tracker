"""Download daily USD to CAD exchange rates from the Bank of Canada and store them.

Uses the Bank of Canada Valet API: free, no API key, data from 2017 onward.
Rates are only published on Canadian business days, so weekends and holidays
have no rate. Any range can be fetched in a single request.
"""

import datetime
import json
from decimal import Decimal

import httpx2
from sqlmodel import Session, func, select

from app.exchange_rates import save_exchange_rate
from app.models import ExchangeRate, Purchase

API_URL = "https://www.bankofcanada.ca/valet"
SERIES = "FXUSDCAD"  # Daily average: Canadian dollars per US dollar


class RateFetchError(Exception):
    """The Bank of Canada API couldn't be reached or returned an error."""


def make_client() -> httpx2.Client:
    return httpx2.Client(base_url=API_URL, timeout=30)


def fetch_rates(
    client: httpx2.Client, start: datetime.date, end: datetime.date
) -> list[tuple[datetime.date, Decimal]]:
    """Download the USD to CAD rate for each business day from start to end (inclusive)."""
    try:
        response = client.get(
            f"/observations/{SERIES}/json",
            params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    except httpx2.HTTPError as error:
        raise RateFetchError(
            f"Could not reach the Bank of Canada ({type(error).__name__})"
        ) from error

    try:
        # parse_float=Decimal keeps any numbers exact; rates arrive as strings anyway.
        data = json.loads(response.text, parse_float=Decimal)
    except ValueError:
        raise RateFetchError(
            f"Unexpected response from the Bank of Canada (HTTP {response.status_code})"
        ) from None

    if response.status_code != 200:
        raise RateFetchError(f"Bank of Canada error: {data.get('message')}")

    return parse_observations(data)


def parse_observations(data: dict) -> list[tuple[datetime.date, Decimal]]:
    """Turn a Valet response into (date, CAD per USD) rows."""
    rows = []
    for observation in data["observations"]:
        value = observation.get(SERIES, {}).get("v")
        if value:  # skip days the Bank lists without a value
            rows.append((datetime.date.fromisoformat(observation["d"]), Decimal(value)))
    return rows


def missing_range(
    session: Session, today: datetime.date
) -> tuple[datetime.date, datetime.date] | None:
    """The dates we still need rates for, or None if we're up to date.

    Starts at the latest stored rate (fetched again in case it changed). With no
    rates stored yet, starts at the earliest purchase, or 30 days ago.
    """
    latest = session.exec(select(func.max(ExchangeRate.date))).one()
    if latest is not None:
        start = latest
    else:
        first_purchase = session.exec(select(func.min(Purchase.purchase_date))).one()
        start = first_purchase or today - datetime.timedelta(days=30)

    if start > today:
        return None
    return start, today


def update_rates(
    session: Session, client: httpx2.Client, start: datetime.date, end: datetime.date
) -> int:
    """Download and store rates for start..end. Returns how many rates were saved."""
    rows = fetch_rates(client, start, end)
    for date, usd_to_cad in rows:
        save_exchange_rate(session, date, usd_to_cad)
    return len(rows)
