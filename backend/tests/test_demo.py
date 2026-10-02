import datetime
from decimal import Decimal

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, price_fetcher, rate_fetcher
from app.models import Currency, Metal, Purchase
from app.portfolio import portfolio_history
from app.seed_demo import DEALER_PREMIUM, SeedError, seed_demo
from tests.test_price_fetcher import FAKE_PRICES, timeseries_response

TODAY = datetime.date(2026, 10, 1)
FAKE_RATE = Decimal("1.40")


def rate_response(request: httpx2.Request) -> httpx2.Response:
    """A USD to CAD rate of 1.40 on weekdays only, like the real Bank of Canada."""
    start = datetime.date.fromisoformat(request.url.params["start_date"])
    end = datetime.date.fromisoformat(request.url.params["end_date"])
    observations = []
    day = start
    while day <= end:
        if day.weekday() < 5:  # no rates on Saturdays and Sundays
            observations.append({"d": day.isoformat(), "FXUSDCAD": {"v": str(FAKE_RATE)}})
        day += datetime.timedelta(days=1)
    return httpx2.Response(200, json={"observations": observations})


def fake(api_url, handler):
    return lambda: httpx2.Client(base_url=api_url, transport=httpx2.MockTransport(handler))


def seed(session: Session) -> list[Purchase]:
    return seed_demo(
        session,
        TODAY,
        fake(rate_fetcher.API_URL, rate_response),
        fake(price_fetcher.API_URL, timeseries_response),
    )


# --- Read-only demo mode ---


@pytest.fixture
def demo_mode(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)


VALID_PURCHASE = {
    "metal": "gold",
    "weight": "1",
    "unit": "troy_oz",
    "purchase_date": "2026-09-15",
    "price_paid": "5000.00",
    "currency": "CAD",
}


def test_settings_report_demo_mode_off_by_default(client: TestClient):
    assert client.get("/settings").json() == {"demo_mode": False}


def test_settings_report_demo_mode_on(client: TestClient, demo_mode):
    assert client.get("/settings").json() == {"demo_mode": True}


def test_demo_mode_blocks_adding_editing_and_deleting(client: TestClient, monkeypatch):
    purchase_id = client.post("/purchases", json=VALID_PURCHASE).json()["id"]
    monkeypatch.setattr(config, "DEMO_MODE", True)

    assert client.post("/purchases", json=VALID_PURCHASE).status_code == 403
    assert client.put(f"/purchases/{purchase_id}", json=VALID_PURCHASE).status_code == 403
    assert client.delete(f"/purchases/{purchase_id}").status_code == 403
    assert len(client.get("/purchases").json()) == 1  # nothing changed


def test_demo_mode_still_allows_reading(client: TestClient, demo_mode):
    assert client.get("/purchases").status_code == 200
    assert client.get("/portfolio/history").status_code == 200
    assert client.get("/portfolio/holdings").status_code == 200


# --- Demo data ---


def test_seed_adds_three_purchases_dated_relative_to_today(session: Session):
    purchases = seed(session)

    assert [(p.metal, p.purchase_date) for p in purchases] == [
        (Metal.GOLD, datetime.date(2026, 7, 18)),  # 75 days before Oct 1
        (Metal.SILVER, datetime.date(2026, 8, 12)),  # 50 days before
        (Metal.PLATINUM, datetime.date(2026, 9, 6)),  # 25 days before
    ]
    assert len(session.exec(select(Purchase)).all()) == 3


def test_seed_prices_purchases_from_spot_plus_premium(session: Session):
    gold, silver, _ = seed(session)

    # 1 oz gold paid in CAD: spot x premium x rate.
    expected_gold = Decimal(str(FAKE_PRICES["gold"])) * DEALER_PREMIUM * FAKE_RATE
    assert gold.currency == Currency.CAD
    assert gold.price_paid == expected_gold.quantize(Decimal("0.01"))

    # 500 g silver paid in USD: no currency conversion.
    expected_silver = Decimal("16.07537400") * Decimal(str(FAKE_PRICES["silver"])) * DEALER_PREMIUM
    assert silver.currency == Currency.USD
    assert silver.price_paid == expected_silver.quantize(Decimal("0.01"))


def test_seed_downloads_market_data_for_the_demo_period(session: Session):
    seed(session)

    history = portfolio_history(session, Currency.CAD, datetime.date(2026, 7, 18), TODAY)
    assert all(day.value is not None for day in history)  # no gaps in the demo chart


def test_seed_refuses_a_database_that_has_purchases(session: Session):
    seed(session)

    with pytest.raises(SeedError, match="already has purchases"):
        seed(session)
