"""Download daily spot prices from metals.dev and store them.

One /timeseries request returns all four metals, in USD per troy ounce, for up
to 30 days. The free plan allows 100 requests a month, so a monthly run costs
about 1 request. We only fetch days we don't have yet (plus the latest stored
day again, in case its price was still changing when we fetched it).
"""

import datetime
import json
import math
from decimal import ROUND_HALF_UP, Decimal

import httpx2
from sqlmodel import Session, func, select

from app.models import Metal, MetalPrice, Purchase
from app.prices import save_metal_price

API_URL = "https://api.metals.dev/v1"
MAX_DAYS_PER_REQUEST = 30
PRICE_PRECISION = Decimal("0.0001")


class PriceFetchError(Exception):
    """The price API couldn't be reached or returned an error."""


def make_client(api_key: str) -> httpx2.Client:
    if not api_key:
        raise PriceFetchError("METALS_DEV_API_KEY is not set. Add it to backend/.env.")
    # metals.dev only accepts the key in the URL, so it's added to every request here.
    # Error messages below never include the URL, so the key can't leak into them.
    return httpx2.Client(base_url=API_URL, params={"api_key": api_key}, timeout=30)


def get_json(client: httpx2.Client, path: str, params: dict | None = None) -> dict:
    """Call the API and return its JSON, raising PriceFetchError on any failure."""
    try:
        response = client.get(path, params=params)
    except httpx2.HTTPError as error:
        # Only the error type: the full message can contain the URL with the API key.
        raise PriceFetchError(
            f"Could not reach metals.dev ({type(error).__name__})"
        ) from None

    try:
        # parse_float=Decimal keeps prices exact instead of turning them into floats.
        data = json.loads(response.text, parse_float=Decimal)
    except ValueError:
        raise PriceFetchError(
            f"Unexpected response from metals.dev (HTTP {response.status_code})"
        ) from None

    if data.get("status") != "success":
        raise PriceFetchError(
            f"metals.dev error {data.get('error_code')}: {data.get('error_message')}"
        )
    return data


def parse_timeseries(data: dict) -> list[tuple[Metal, datetime.date, Decimal]]:
    """Turn a /timeseries response into (metal, date, USD per troy ounce) rows."""
    # We store USD per troy ounce, so refuse anything else rather than save wrong prices.
    if data.get("currency") != "USD" or data.get("unit") != "toz":
        raise PriceFetchError(
            f"Expected prices in USD per troy ounce, got {data.get('currency')} "
            f"per {data.get('unit')}"
        )

    rows = []
    for day, entry in data["rates"].items():
        date = datetime.date.fromisoformat(day)
        # The API names metals "gold", "silver", ... the same as our Metal values.
        for metal in Metal:
            price = entry["metals"].get(metal.value)
            if price is not None:
                price = Decimal(price).quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)
                rows.append((metal, date, price))
    return rows


def fetch_prices(
    client: httpx2.Client, start: datetime.date, end: datetime.date
) -> list[tuple[Metal, datetime.date, Decimal]]:
    """Download all metals' prices from start to end (inclusive).

    Each request covers at most 30 days, so longer ranges are split up.
    """
    rows = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + datetime.timedelta(days=MAX_DAYS_PER_REQUEST - 1), end)
        data = get_json(
            client,
            "/timeseries",
            params={"start_date": chunk_start.isoformat(), "end_date": chunk_end.isoformat()},
        )
        rows.extend(parse_timeseries(data))
        chunk_start = chunk_end + datetime.timedelta(days=1)
    return rows


def requests_needed(start: datetime.date, end: datetime.date) -> int:
    """How many API requests fetching start..end will use (one per 30 days)."""
    days = (end - start).days + 1
    return math.ceil(days / MAX_DAYS_PER_REQUEST)


def missing_range(
    session: Session, today: datetime.date
) -> tuple[datetime.date, datetime.date] | None:
    """The dates we still need prices for, or None if we're up to date.

    Starts at the latest day that every metal has a price for. That day is
    fetched again because its price may have been fetched before the day ended.
    With no prices stored yet, starts at the earliest purchase, or 30 days ago
    if there are no purchases.
    """
    latest_per_metal = [
        session.exec(select(func.max(MetalPrice.date)).where(MetalPrice.metal == metal)).one()
        for metal in Metal
    ]

    if None not in latest_per_metal:
        start = min(latest_per_metal)
    else:
        first_purchase = session.exec(select(func.min(Purchase.purchase_date))).one()
        start = first_purchase or today - datetime.timedelta(days=30)

    if start > today:
        return None
    return start, today


def update_prices(
    session: Session,
    client: httpx2.Client,
    start: datetime.date,
    end: datetime.date,
) -> int:
    """Download and store prices for start..end. Returns how many prices were saved."""
    rows = fetch_prices(client, start, end)
    for metal, date, price in rows:
        save_metal_price(session, metal, date, price)
    return len(rows)
