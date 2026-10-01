import datetime
from decimal import Decimal

import httpx2
import pytest
from sqlmodel import Session, select

from app.models import Currency, Metal, MetalPrice, Purchase
from app.price_fetcher import (
    API_URL,
    PriceFetchError,
    fetch_prices,
    get_json,
    make_client,
    missing_range,
    parse_timeseries,
    requests_needed,
    update_prices,
)
from app.prices import save_metal_price
from app.units import WeightUnit

TODAY = datetime.date(2026, 10, 1)

# USD per troy ounce returned by the fake API for every day.
FAKE_PRICES = {"gold": 4007.585, "silver": 56.41945, "platinum": 1589.7, "palladium": 1252.893}


def fake_client(handler) -> httpx2.Client:
    """A client that sends requests to `handler` instead of the real API."""
    return httpx2.Client(base_url=API_URL, transport=httpx2.MockTransport(handler))


def timeseries_response(request: httpx2.Request) -> httpx2.Response:
    """Answer /timeseries like metals.dev: all four metals for every requested day."""
    start = datetime.date.fromisoformat(request.url.params["start_date"])
    end = datetime.date.fromisoformat(request.url.params["end_date"])
    rates = {}
    day = start
    while day <= end:
        rates[day.isoformat()] = {
            "currencies": {"CAD": 0.7097, "USD": 1},
            "date": day.isoformat(),
            "metals": FAKE_PRICES,
        }
        day += datetime.timedelta(days=1)
    body = {"status": "success", "currency": "USD", "unit": "toz", "rates": rates}
    return httpx2.Response(200, json=body)


def error_response(code: int, message: str) -> httpx2.Response:
    body = {"status": "failure", "error_code": code, "error_message": message}
    return httpx2.Response(200, json=body)


# --- Reading prices out of a response ---


def test_parse_timeseries_reads_a_real_response():
    # Shape of a real metals.dev response (July 20, 2026), trimmed.
    data = {
        "status": "success",
        "currency": "USD",
        "unit": "toz",
        "start_date": "2026-07-20",
        "end_date": "2026-07-20",
        "rates": {
            "2026-07-20": {
                "currencies": {"CAD": Decimal("0.7097"), "USD": 1},
                "date": "2026-07-20",
                "metals": {
                    "gold": Decimal("4007.585"),
                    "palladium": Decimal("1252.893"),
                    "platinum": Decimal("1589.7"),
                    "silver": Decimal("56.41945"),
                },
            }
        },
    }

    rows = parse_timeseries(data)

    july_20 = datetime.date(2026, 7, 20)
    assert rows == [
        (Metal.GOLD, july_20, Decimal("4007.5850")),
        (Metal.SILVER, july_20, Decimal("56.4195")),
        (Metal.PLATINUM, july_20, Decimal("1589.7000")),
        (Metal.PALLADIUM, july_20, Decimal("1252.8930")),
    ]


def test_parse_timeseries_skips_a_missing_metal():
    data = {
        "currency": "USD",
        "unit": "toz",
        "rates": {"2026-07-20": {"metals": {"gold": Decimal("4000")}}},
    }

    assert [metal for metal, _, _ in parse_timeseries(data)] == [Metal.GOLD]


def test_parse_timeseries_refuses_other_currencies_or_units():
    data = {"currency": "EUR", "unit": "g", "rates": {}}

    with pytest.raises(PriceFetchError, match="USD per troy ounce"):
        parse_timeseries(data)


# --- Talking to the API ---


def test_make_client_requires_an_api_key():
    with pytest.raises(PriceFetchError, match="METALS_DEV_API_KEY"):
        make_client("")


def test_make_client_adds_key_to_every_request():
    client = make_client("secret-key")

    assert client.params["api_key"] == "secret-key"


def test_fetch_prices_requests_the_date_range():
    requests = []

    def handler(request):
        requests.append(request)
        return timeseries_response(request)

    rows = fetch_prices(fake_client(handler), datetime.date(2026, 9, 1), datetime.date(2026, 9, 3))

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/timeseries"
    assert requests[0].url.params["start_date"] == "2026-09-01"
    assert requests[0].url.params["end_date"] == "2026-09-03"
    assert len(rows) == 3 * 4  # 3 days x 4 metals


def test_fetch_prices_splits_ranges_longer_than_30_days():
    requested = []

    def handler(request):
        requested.append((request.url.params["start_date"], request.url.params["end_date"]))
        return timeseries_response(request)

    fetch_prices(fake_client(handler), datetime.date(2026, 7, 10), datetime.date(2026, 10, 1))

    assert requested == [
        ("2026-07-10", "2026-08-08"),
        ("2026-08-09", "2026-09-07"),
        ("2026-09-08", "2026-10-01"),
    ]


def test_requests_needed_is_one_per_30_days():
    july_10 = datetime.date(2026, 7, 10)

    assert requests_needed(july_10, july_10) == 1
    assert requests_needed(july_10, datetime.date(2026, 8, 8)) == 1  # 30 days
    assert requests_needed(july_10, datetime.date(2026, 8, 9)) == 2  # 31 days
    assert requests_needed(july_10, datetime.date(2026, 10, 1)) == 3  # 84 days


def test_api_error_is_raised_with_its_message():
    def handler(request):
        return error_response(1101, "Unauthorized. The API Key provided is invalid.")

    with pytest.raises(PriceFetchError, match="1101: Unauthorized"):
        get_json(fake_client(handler), "/timeseries")


def test_non_json_response_is_reported():
    def handler(request):
        return httpx2.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(PriceFetchError, match="HTTP 502"):
        get_json(fake_client(handler), "/timeseries")


def test_network_errors_do_not_reveal_the_api_key():
    def handler(request):
        raise httpx2.ConnectError(f"connection refused for {request.url}")

    client = fake_client(handler)
    client.params = {"api_key": "secret-key"}

    with pytest.raises(PriceFetchError) as error:
        get_json(client, "/timeseries")

    assert "Could not reach metals.dev" in str(error.value)
    assert "secret-key" not in str(error.value)
    assert error.value.__cause__ is None  # the original error (with the URL) isn't attached


# --- Working out which days are missing ---


def save_all_metals(session: Session, date: datetime.date):
    for metal in Metal:
        save_metal_price(session, metal, date, Decimal("100"))


def test_missing_range_refetches_the_latest_stored_day(session: Session):
    save_all_metals(session, datetime.date(2026, 9, 20))

    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 20), TODAY)


def test_missing_range_catches_up_a_metal_that_is_behind(session: Session):
    save_all_metals(session, datetime.date(2026, 9, 20))
    for metal in [Metal.GOLD, Metal.SILVER, Metal.PLATINUM]:  # palladium stays behind
        save_metal_price(session, metal, datetime.date(2026, 9, 25), Decimal("100"))

    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 20), TODAY)


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
    # Sept 2 to Oct 1 is 30 days including today.
    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 2), TODAY)


def test_missing_range_is_none_when_prices_are_ahead_of_today(session: Session):
    save_all_metals(session, TODAY + datetime.timedelta(days=1))

    assert missing_range(session, TODAY) is None


# --- Storing ---


def test_update_prices_stores_every_price(session: Session):
    client = fake_client(timeseries_response)

    saved = update_prices(session, client, datetime.date(2026, 9, 1), datetime.date(2026, 9, 3))

    prices = session.exec(select(MetalPrice)).all()
    assert saved == 12  # 4 metals x 3 days
    assert len(prices) == 12
    assert {p.spot_price_usd for p in prices} == {
        Decimal("4007.5850"),
        Decimal("56.4195"),
        Decimal("1589.7000"),
        Decimal("1252.8930"),
    }


def test_fetching_the_same_days_twice_does_not_duplicate(session: Session):
    client = fake_client(timeseries_response)
    start, end = datetime.date(2026, 9, 1), datetime.date(2026, 9, 3)

    update_prices(session, client, start, end)
    update_prices(session, client, start, end)

    assert len(session.exec(select(MetalPrice)).all()) == 12
