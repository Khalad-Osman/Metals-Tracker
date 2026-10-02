import datetime
from decimal import Decimal

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, price_fetcher, rate_fetcher
from app.models import Currency, Metal, Purchase
from app.prices import save_metal_price
from app.reset_demo import ResetRefused, reset_demo
from app.units import WeightUnit
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


# --- Demo modes ---


VALID_PURCHASE = {
    "metal": "gold",
    "weight": "1",
    "unit": "troy_oz",
    "purchase_date": "2026-09-15",
    "price_paid": "5000.00",
    "currency": "CAD",
}


@pytest.mark.parametrize(
    "setting, mode",
    [
        ("", "off"),
        ("false", "off"),
        ("off", "off"),
        ("true", "readonly"),  # what the live demo used before sandbox mode existed
        ("readonly", "readonly"),
        ("sandbox", "sandbox"),
        (" Sandbox ", "sandbox"),
        ("typo", "readonly"),  # unknown values fall back to the safe choice
    ],
)
def test_parse_demo_mode(setting, mode):
    assert config.parse_demo_mode(setting) == mode


@pytest.mark.parametrize("mode", ["off", "readonly", "sandbox"])
def test_settings_report_the_demo_mode(client: TestClient, monkeypatch, mode):
    monkeypatch.setattr(config, "DEMO_MODE", mode)

    assert client.get("/settings").json() == {"demo_mode": mode}


def test_read_only_demo_blocks_adding_editing_and_deleting(client: TestClient, monkeypatch):
    purchase_id = client.post("/purchases", json=VALID_PURCHASE).json()["id"]
    monkeypatch.setattr(config, "DEMO_MODE", "readonly")

    assert client.post("/purchases", json=VALID_PURCHASE).status_code == 403
    assert client.put(f"/purchases/{purchase_id}", json=VALID_PURCHASE).status_code == 403
    assert client.delete(f"/purchases/{purchase_id}").status_code == 403
    assert len(client.get("/purchases").json()) == 1  # nothing changed


def test_read_only_demo_still_allows_reading(client: TestClient, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", "readonly")

    assert client.get("/purchases").status_code == 200
    assert client.get("/portfolio/history").status_code == 200
    assert client.get("/portfolio/holdings").status_code == 200


# --- Sandbox demo ---


@pytest.fixture
def sandbox(session: Session, monkeypatch):
    """Sandbox mode, with gold prices stored from Sept 1."""
    monkeypatch.setattr(config, "DEMO_MODE", "sandbox")
    save_metal_price(session, Metal.GOLD, datetime.date(2026, 9, 1), Decimal("4000"))


def field_errors(response) -> dict[str, str]:
    return {error["loc"][-1]: error["msg"] for error in response.json()["detail"]}


def test_sandbox_allows_adding_editing_and_deleting(client: TestClient, sandbox):
    added = client.post("/purchases", json=VALID_PURCHASE)
    purchase_id = added.json()["id"]
    edited = client.put(f"/purchases/{purchase_id}", json={**VALID_PURCHASE, "weight": "2"})
    deleted = client.delete(f"/purchases/{purchase_id}")

    assert (added.status_code, edited.status_code, deleted.status_code) == (201, 200, 204)


def test_sandbox_limits_weight_to_100_kg(client: TestClient, sandbox):
    ok = client.post("/purchases", json={**VALID_PURCHASE, "weight": "100", "unit": "kg"})
    too_heavy = client.post("/purchases", json={**VALID_PURCHASE, "weight": "101", "unit": "kg"})

    assert ok.status_code == 201
    assert too_heavy.status_code == 422
    assert field_errors(too_heavy) == {"weight": "The demo allows up to 100 kg"}


def test_sandbox_limits_price(client: TestClient, sandbox):
    response = client.post("/purchases", json={**VALID_PURCHASE, "price_paid": "1000000.01"})

    assert response.status_code == 422
    assert field_errors(response) == {"price_paid": "The demo allows prices up to 1,000,000"}


def test_sandbox_rejects_dates_before_the_demo_has_prices(client: TestClient, sandbox):
    response = client.post("/purchases", json={**VALID_PURCHASE, "purchase_date": "2026-08-31"})

    assert response.status_code == 422
    assert field_errors(response) == {"purchase_date": "The demo only has prices from 2026-09-01"}


def test_sandbox_rejects_metals_without_any_prices(client: TestClient, sandbox):
    response = client.post("/purchases", json={**VALID_PURCHASE, "metal": "palladium"})

    assert response.status_code == 422
    assert "purchase_date" in field_errors(response)


def test_sandbox_is_full_at_50_purchases(client: TestClient, session: Session, sandbox):
    for _ in range(50):
        session.add(
            Purchase.from_entry(
                metal=Metal.GOLD,
                weight=Decimal("1"),
                unit=WeightUnit.TROY_OUNCE,
                purchase_date=datetime.date(2026, 9, 15),
                price_paid=Decimal("5000"),
                currency=Currency.CAD,
            )
        )
    session.commit()

    full = client.post("/purchases", json=VALID_PURCHASE)
    edit_still_allowed = client.put("/purchases/1", json={**VALID_PURCHASE, "weight": "2"})

    assert full.status_code == 409
    assert "The demo is full" in full.json()["detail"]
    assert edit_still_allowed.status_code == 200


def test_normal_mode_has_no_sandbox_limits(client: TestClient):
    response = client.post("/purchases", json={**VALID_PURCHASE, "weight": "500", "unit": "kg"})

    assert response.status_code == 201


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


# --- Nightly reset ---


def test_reset_replaces_all_purchases_with_the_samples(session: Session, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", "sandbox")
    seed(session)
    session.add(  # a visitor's purchase
        Purchase.from_entry(
            metal=Metal.SILVER,
            weight=Decimal("5"),
            unit=WeightUnit.KILOGRAM,
            purchase_date=datetime.date(2026, 9, 20),
            price_paid=Decimal("9999"),
            currency=Currency.USD,
        )
    )
    session.commit()

    reset_demo(session, TODAY)

    purchases = session.exec(select(Purchase)).all()
    assert [(p.metal, p.purchase_date) for p in purchases] == [
        (Metal.GOLD, datetime.date(2026, 7, 18)),
        (Metal.SILVER, datetime.date(2026, 8, 12)),
        (Metal.PLATINUM, datetime.date(2026, 9, 6)),
    ]


def test_reset_dates_the_samples_relative_to_the_reset_day(session: Session, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", "sandbox")
    seed(session)

    reset_demo(session, TODAY + datetime.timedelta(days=1))  # the next night, no new downloads

    gold = session.exec(select(Purchase).where(Purchase.metal == Metal.GOLD)).one()
    assert gold.purchase_date == datetime.date(2026, 7, 19)


def test_reset_refuses_when_demo_mode_is_off(session: Session):
    seed(session)

    with pytest.raises(ResetRefused, match="nothing was deleted"):
        reset_demo(session, TODAY)

    assert len(session.exec(select(Purchase)).all()) == 3  # untouched
