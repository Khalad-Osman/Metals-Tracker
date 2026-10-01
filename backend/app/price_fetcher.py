"""Download daily spot prices from metalpriceapi.com and store them.

Free plan limits (found by testing; the docs don't mention most of them):
- 100 requests a month
- each /timeframe request covers one metal and at most 5 days
- prices only go back 30 days
So fetching costs 4 requests (one per metal) per 5 days. We only fetch days we
don't have yet.
"""

import datetime
import json
import math
from decimal import Decimal

import httpx2
from sqlmodel import Session, func, select

from app.models import Metal, MetalPrice, Purchase
from app.prices import save_metal_price

API_URL = "https://api.metalpriceapi.com/v1"
# Free plan: at most 5 days per /timeframe request, and only the last 30 days.
MAX_DAYS_PER_REQUEST = 5
FREE_PLAN_HISTORY_DAYS = 30
PRICE_PRECISION = Decimal("0.0001")

# The API's symbol for each metal.
SYMBOLS = {
    Metal.GOLD: "XAU",
    Metal.SILVER: "XAG",
    Metal.PLATINUM: "XPT",
    Metal.PALLADIUM: "XPD",
}


class PriceFetchError(Exception):
    """The price API couldn't be reached or returned an error."""


def make_client(api_key: str) -> httpx2.Client:
    if not api_key:
        raise PriceFetchError("METALS_API_KEY is not set. Add it to backend/.env.")
    # Send the key in a header rather than the URL, so it doesn't show up in logs.
    return httpx2.Client(base_url=API_URL, headers={"X-API-KEY": api_key}, timeout=30)


def get_json(client: httpx2.Client, path: str, params: dict | None = None) -> dict:
    """Call the API and return its JSON, raising PriceFetchError on any failure."""
    try:
        response = client.get(path, params=params)
    except httpx2.HTTPError as error:
        raise PriceFetchError(f"Could not reach metalpriceapi.com: {error}") from error

    try:
        # parse_float=Decimal keeps prices exact instead of turning them into floats.
        data = json.loads(response.text, parse_float=Decimal)
    except ValueError as error:
        raise PriceFetchError(
            f"Unexpected response from metalpriceapi.com (HTTP {response.status_code})"
        ) from error

    if not data.get("success"):
        # The docs describe {"code", "info"}, but the API also sends {"statusCode", "message"}.
        error = data.get("error", {})
        code = error.get("code") or error.get("statusCode")
        message = error.get("info") or error.get("message")
        raise PriceFetchError(f"metalpriceapi.com error {code}: {message}")
    return data


def check_usage(client: httpx2.Client) -> dict:
    """Plan name and requests used/remaining this month. Doesn't use up any quota."""
    return get_json(client, "/usage")["result"]


def usd_per_ounce(rates: dict, symbol: str) -> Decimal | None:
    """Read a metal's price in USD per troy ounce from one day's rates.

    The API quotes "ounces per 1 USD" (e.g. XAU: 0.00056) and usually also the
    inverse, USD per ounce (e.g. USDXAU: 1783.23). Use the inverse when present.
    """
    if f"USD{symbol}" in rates:
        price = Decimal(rates[f"USD{symbol}"])
    elif rates.get(symbol):
        price = 1 / Decimal(rates[symbol])
    else:
        return None
    return price.quantize(PRICE_PRECISION)


def parse_timeframe(data: dict) -> list[tuple[Metal, datetime.date, Decimal]]:
    """Turn a /timeframe response into (metal, date, USD per ounce) rows."""
    rows = []
    for day, rates in data["rates"].items():
        date = datetime.date.fromisoformat(day)
        for metal, symbol in SYMBOLS.items():
            price = usd_per_ounce(rates, symbol)
            if price is not None:
                rows.append((metal, date, price))
    return rows


def fetch_prices(
    client: httpx2.Client, metal: Metal, start: datetime.date, end: datetime.date
) -> list[tuple[Metal, datetime.date, Decimal]]:
    """Download one metal's prices from start to end (inclusive).

    The free plan allows only one metal per /timeframe request, and each request
    covers at most 5 days, so longer ranges are split into several requests.
    """
    rows = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + datetime.timedelta(days=MAX_DAYS_PER_REQUEST - 1), end)
        data = get_json(
            client,
            "/timeframe",
            params={
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
                "base": "USD",
                "currencies": SYMBOLS[metal],
            },
        )
        rows.extend(parse_timeframe(data))
        chunk_start = chunk_end + datetime.timedelta(days=1)
    return rows


def requests_needed(start: datetime.date, end: datetime.date) -> int:
    """How many API requests fetching start..end will use (one per metal per 5 days)."""
    days = (end - start).days + 1
    return len(SYMBOLS) * math.ceil(days / MAX_DAYS_PER_REQUEST)


def earliest_free_plan_date(today: datetime.date) -> datetime.date:
    """The oldest date the free plan will return prices for.

    The API rejects anything "older than 30 days". We stay one day inside that,
    in case the API's "today" (UTC) is already a day ahead of ours.
    """
    return today - datetime.timedelta(days=FREE_PLAN_HISTORY_DAYS - 1)


def missing_range(
    session: Session, today: datetime.date
) -> tuple[datetime.date, datetime.date] | None:
    """The dates we still need prices for, or None if we're up to date.

    Starts the day after the latest price that every metal has (so a metal that
    failed to download last time gets filled in). With no prices stored yet,
    starts at the earliest purchase, or 30 days ago if there are no purchases.
    """
    latest_per_metal = [
        session.exec(select(func.max(MetalPrice.date)).where(MetalPrice.metal == metal)).one()
        for metal in Metal
    ]

    if None not in latest_per_metal:
        start = min(latest_per_metal) + datetime.timedelta(days=1)
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
    """Download and store all metals' prices for start..end.

    Each metal is saved as soon as it downloads, so if a later request fails,
    the requests already made aren't wasted. Returns how many prices were saved.
    """
    saved = 0
    for metal in SYMBOLS:
        for row_metal, date, price in fetch_prices(client, metal, start, end):
            save_metal_price(session, row_metal, date, price)
            saved += 1
    return saved
