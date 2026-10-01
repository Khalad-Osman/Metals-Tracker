import datetime
from decimal import Decimal

import httpx2
import pytest
from sqlmodel import Session, select

from app.models import Currency, Metal, MetalPrice, Purchase
from app.price_fetcher import (
    API_URL,
    PriceFetchError,
    check_usage,
    fetch_prices,
    make_client,
    missing_range,
    parse_timeframe,
    update_prices,
    usd_per_ounce,
)
from app.prices import save_metal_price
from app.units import WeightUnit

TODAY = datetime.date(2026, 10, 1)


def fake_client(handler) -> httpx2.Client:
    """A client that sends requests to `handler` instead of the real API."""
    return httpx2.Client(base_url=API_URL, transport=httpx2.MockTransport(handler))


def timeframe_response(request: httpx2.Request) -> httpx2.Response:
    """Answer /timeframe with one fixed gold and silver price per requested day."""
    start = datetime.date.fromisoformat(request.url.params["start_date"])
    end = datetime.date.fromisoformat(request.url.params["end_date"])
    rates = {}
    day = start
    while day <= end:
        rates[day.isoformat()] = {
            "XAU": 0.00037736,
            "USDXAU": 2650.0,
            "XAG": 0.032,
            "USDXAG": 31.25,
        }
        day += datetime.timedelta(days=1)
    return httpx2.Response(200, json={"success": True, "base": "USD", "rates": rates})


# --- Reading prices out of a response ---


def test_usd_per_ounce_uses_the_inverse_field_when_present():
    rates = {"XAU": Decimal("0.00056078"), "USDXAU": Decimal("1783.2305")}

    assert usd_per_ounce(rates, "XAU") == Decimal("1783.2305")


def test_usd_per_ounce_calculates_the_inverse_when_missing():
    rates = {"XAU": Decimal("0.0004")}

    assert usd_per_ounce(rates, "XAU") == Decimal("2500.0000")


def test_usd_per_ounce_returns_none_when_metal_missing():
    assert usd_per_ounce({"XAU": Decimal("0.0004")}, "XPT") is None


def test_parse_timeframe_reads_the_documented_example():
    # Example response from the metalpriceapi.com documentation.
    data = {
        "success": True,
        "base": "USD",
        "start_date": "2021-04-22",
        "end_date": "2021-04-23",
        "rates": {
            "2021-04-22": {
                "XAG": Decimal("0.03825732"),
                "XAU": Decimal("0.00056078"),
                "USDXAG": Decimal("26.1387886"),
                "USDXAU": Decimal("1783.2305"),
            },
            "2021-04-23": {"XAU": Decimal("0.0005628")},
        },
    }

    rows = parse_timeframe(data)

    assert rows == [
        (Metal.GOLD, datetime.date(2021, 4, 22), Decimal("1783.2305")),
        (Metal.SILVER, datetime.date(2021, 4, 22), Decimal("26.1388")),
        (Metal.GOLD, datetime.date(2021, 4, 23), Decimal("1776.8301")),
    ]


# --- Talking to the API ---


def test_make_client_requires_an_api_key():
    with pytest.raises(PriceFetchError, match="METALS_API_KEY"):
        make_client("")


def test_make_client_sends_key_in_header_not_url():
    client = make_client("secret-key")

    assert client.headers["X-API-KEY"] == "secret-key"
    assert "secret-key" not in str(client.base_url)


def test_fetch_prices_asks_for_all_four_metals_in_usd():
    requests = []

    def handler(request):
        requests.append(request)
        return timeframe_response(request)

    fetch_prices(fake_client(handler), datetime.date(2026, 9, 1), datetime.date(2026, 9, 3))

    params = requests[0].url.params
    assert requests[0].url.path == "/v1/timeframe"
    assert params["base"] == "USD"
    assert params["currencies"] == "XAU,XAG,XPT,XPD"


def test_fetch_prices_splits_ranges_longer_than_365_days():
    requested = []

    def handler(request):
        requested.append((request.url.params["start_date"], request.url.params["end_date"]))
        return timeframe_response(request)

    rows = fetch_prices(fake_client(handler), datetime.date(2025, 1, 1), datetime.date(2026, 1, 10))

    assert requested == [("2025-01-01", "2025-12-31"), ("2026-01-01", "2026-01-10")]
    assert len(rows) == (365 + 10) * 2  # gold and silver for every day


def test_api_error_is_raised_with_its_message():
    def handler(request):
        return httpx2.Response(
            200, json={"success": False, "error": {"code": 102, "info": "Invalid API Key"}}
        )

    with pytest.raises(PriceFetchError, match="102: Invalid API Key"):
        check_usage(fake_client(handler))


def test_non_json_response_is_reported():
    def handler(request):
        return httpx2.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(PriceFetchError, match="HTTP 502"):
        check_usage(fake_client(handler))


def test_network_failure_is_reported():
    def handler(request):
        raise httpx2.ConnectError("connection refused")

    with pytest.raises(PriceFetchError, match="Could not reach"):
        check_usage(fake_client(handler))


def test_check_usage_returns_plan_details():
    def handler(request):
        result = {"plan": "Free", "used": 3, "total": 100, "remaining": 97}
        return httpx2.Response(200, json={"success": True, "result": result})

    assert check_usage(fake_client(handler))["remaining"] == 97


# --- Working out which days are missing ---


def test_missing_range_starts_after_latest_stored_price(session: Session):
    save_metal_price(session, Metal.GOLD, datetime.date(2026, 9, 20), Decimal("2650"))

    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 21), TODAY)


def test_missing_range_starts_at_first_purchase_when_no_prices(session: Session):
    session.add(
        Purchase.from_entry(
            metal=Metal.GOLD,
            weight=Decimal("1"),
            unit=WeightUnit.TROY_OUNCE,
            purchase_date=datetime.date(2026, 6, 1),
            price_paid=Decimal("3000"),
            currency=Currency.USD,
        )
    )
    session.commit()

    assert missing_range(session, TODAY) == (datetime.date(2026, 6, 1), TODAY)


def test_missing_range_defaults_to_last_30_days(session: Session):
    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 1), TODAY)


def test_missing_range_is_none_when_up_to_date(session: Session):
    save_metal_price(session, Metal.GOLD, TODAY, Decimal("2650"))

    assert missing_range(session, TODAY) is None


# --- Storing ---


def test_update_prices_stores_every_price(session: Session):
    client = fake_client(timeframe_response)

    saved = update_prices(session, client, datetime.date(2026, 9, 1), datetime.date(2026, 9, 3))

    prices = session.exec(select(MetalPrice)).all()
    assert saved == 6
    assert len(prices) == 6
    assert {p.spot_price_usd for p in prices} == {Decimal("2650.0000"), Decimal("31.2500")}


def test_fetching_the_same_days_twice_does_not_duplicate(session: Session):
    client = fake_client(timeframe_response)
    start, end = datetime.date(2026, 9, 1), datetime.date(2026, 9, 3)

    update_prices(session, client, start, end)
    update_prices(session, client, start, end)

    assert len(session.exec(select(MetalPrice)).all()) == 6
