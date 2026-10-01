import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Metal
from app.prices import save_metal_price


@pytest.fixture
def sample_prices(session: Session):
    """Gold and silver prices for three days in September 2026."""
    for day, gold, silver in [
        (14, "2640.00", "31.10"),
        (15, "2650.50", "31.25"),
        (16, "2661.75", "31.40"),
    ]:
        date = datetime.date(2026, 9, day)
        save_metal_price(session, Metal.GOLD, date, Decimal(gold))
        save_metal_price(session, Metal.SILVER, date, Decimal(silver))


def test_no_prices_stored_returns_empty_list(client: TestClient):
    response = client.get("/prices")

    assert response.status_code == 200
    assert response.json() == []


def test_price_response_shape(client: TestClient, sample_prices):
    response = client.get("/prices", params={"metal": "gold", "start": "2026-09-15", "end": "2026-09-15"})

    assert response.json() == [
        {"metal": "gold", "date": "2026-09-15", "spot_price_usd": "2650.5000"}
    ]


def test_lists_all_prices_oldest_first(client: TestClient, sample_prices):
    prices = client.get("/prices").json()

    assert len(prices) == 6
    assert [p["date"] for p in prices] == sorted(p["date"] for p in prices)


def test_filter_by_metal(client: TestClient, sample_prices):
    prices = client.get("/prices", params={"metal": "silver"}).json()

    assert [p["spot_price_usd"] for p in prices] == ["31.1000", "31.2500", "31.4000"]


def test_filter_by_date_range_includes_both_ends(client: TestClient, sample_prices):
    prices = client.get(
        "/prices", params={"metal": "gold", "start": "2026-09-15", "end": "2026-09-16"}
    ).json()

    assert [p["date"] for p in prices] == ["2026-09-15", "2026-09-16"]


def test_unknown_metal_is_rejected(client: TestClient):
    response = client.get("/prices", params={"metal": "copper"})

    assert response.status_code == 422


def test_invalid_date_is_rejected(client: TestClient):
    response = client.get("/prices", params={"start": "not-a-date"})

    assert response.status_code == 422
