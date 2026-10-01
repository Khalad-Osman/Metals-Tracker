import datetime
from decimal import Decimal

import httpx2
import pytest
from sqlmodel import Session, select

from app.exchange_rates import save_exchange_rate
from app.models import Currency, ExchangeRate, Metal, Purchase
from app.rate_fetcher import (
    API_URL,
    RateFetchError,
    fetch_rates,
    missing_range,
    parse_observations,
    update_rates,
)
from app.units import WeightUnit

TODAY = datetime.date(2026, 10, 1)


def fake_client(handler) -> httpx2.Client:
    """A client that sends requests to `handler` instead of the real API."""
    return httpx2.Client(base_url=API_URL, transport=httpx2.MockTransport(handler))


def valet_response(observations: list[tuple[str, str]]) -> httpx2.Response:
    body = {
        "observations": [{"d": day, "FXUSDCAD": {"v": value}} for day, value in observations]
    }
    return httpx2.Response(200, json=body)


# A real stretch from early September 2026: the 5th-6th are a weekend and
# the 7th is Labour Day, so the Bank of Canada published no rate on those days.
EARLY_SEPTEMBER = [
    ("2026-09-01", "1.3896"),
    ("2026-09-02", "1.3863"),
    ("2026-09-03", "1.3789"),
    ("2026-09-04", "1.3840"),
    ("2026-09-08", "1.3784"),
]


# --- Reading rates out of a response ---


def test_parse_observations_reads_rates_as_decimals():
    data = valet_response(EARLY_SEPTEMBER[:2]).json()

    assert parse_observations(data) == [
        (datetime.date(2026, 9, 1), Decimal("1.3896")),
        (datetime.date(2026, 9, 2), Decimal("1.3863")),
    ]


def test_parse_observations_skips_days_without_a_value():
    data = {"observations": [{"d": "2026-09-01", "FXUSDCAD": {"v": ""}}, {"d": "2026-09-02"}]}

    assert parse_observations(data) == []


# --- Talking to the API ---


def test_fetch_rates_requests_the_usd_cad_series_for_the_range():
    requests = []

    def handler(request):
        requests.append(request)
        return valet_response(EARLY_SEPTEMBER)

    rows = fetch_rates(fake_client(handler), datetime.date(2026, 9, 1), datetime.date(2026, 9, 8))

    assert len(requests) == 1
    assert requests[0].url.path == "/valet/observations/FXUSDCAD/json"
    assert requests[0].url.params["start_date"] == "2026-09-01"
    assert requests[0].url.params["end_date"] == "2026-09-08"
    assert len(rows) == 5  # business days only


def test_a_weekend_with_no_rates_is_not_an_error():
    rows = fetch_rates(
        fake_client(lambda request: valet_response([])),
        datetime.date(2026, 9, 5),
        datetime.date(2026, 9, 6),
    )

    assert rows == []


def test_api_error_is_raised_with_its_message():
    def handler(request):
        return httpx2.Response(400, json={"message": "Start date contains a value that is not allowed."})

    with pytest.raises(RateFetchError, match="Start date contains a value"):
        fetch_rates(fake_client(handler), TODAY, TODAY)


def test_non_json_response_is_reported():
    def handler(request):
        return httpx2.Response(503, text="<html>Service Unavailable</html>")

    with pytest.raises(RateFetchError, match="HTTP 503"):
        fetch_rates(fake_client(handler), TODAY, TODAY)


def test_network_failure_is_reported():
    def handler(request):
        raise httpx2.ConnectError("connection refused")

    with pytest.raises(RateFetchError, match="Could not reach the Bank of Canada"):
        fetch_rates(fake_client(handler), TODAY, TODAY)


# --- Working out which days are missing ---


def test_missing_range_refetches_the_latest_stored_day(session: Session):
    save_exchange_rate(session, datetime.date(2026, 9, 29), Decimal("1.4188"))

    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 29), TODAY)


def test_missing_range_starts_at_first_purchase_when_no_rates(session: Session):
    session.add(
        Purchase.from_entry(
            metal=Metal.GOLD,
            weight=Decimal("1"),
            unit=WeightUnit.TROY_OUNCE,
            purchase_date=datetime.date(2026, 7, 20),
            price_paid=Decimal("5500"),
            currency=Currency.CAD,
        )
    )
    session.commit()

    assert missing_range(session, TODAY) == (datetime.date(2026, 7, 20), TODAY)


def test_missing_range_defaults_to_last_30_days(session: Session):
    assert missing_range(session, TODAY) == (datetime.date(2026, 9, 1), TODAY)


def test_missing_range_is_none_when_rates_are_ahead_of_today(session: Session):
    save_exchange_rate(session, TODAY + datetime.timedelta(days=1), Decimal("1.4"))

    assert missing_range(session, TODAY) is None


# --- Storing ---


def test_update_rates_stores_every_business_day(session: Session):
    client = fake_client(lambda request: valet_response(EARLY_SEPTEMBER))

    saved = update_rates(session, client, datetime.date(2026, 9, 1), datetime.date(2026, 9, 8))

    stored = session.exec(select(ExchangeRate).order_by(ExchangeRate.date)).all()
    assert saved == 5
    assert [r.date.day for r in stored] == [1, 2, 3, 4, 8]
    assert stored[0].usd_to_cad == Decimal("1.3896")


def test_fetching_the_same_days_twice_does_not_duplicate(session: Session):
    client = fake_client(lambda request: valet_response(EARLY_SEPTEMBER))
    start, end = datetime.date(2026, 9, 1), datetime.date(2026, 9, 8)

    update_rates(session, client, start, end)
    update_rates(session, client, start, end)

    assert len(session.exec(select(ExchangeRate)).all()) == 5
