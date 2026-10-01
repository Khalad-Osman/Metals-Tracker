import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.exchange_rates import save_exchange_rate
from app.models import ExchangeRate

SEPT_15 = datetime.date(2026, 9, 15)


# --- Saving ---


def test_save_exchange_rate_stores_a_new_rate(session: Session):
    save_exchange_rate(session, SEPT_15, Decimal("1.3845"))

    rate = session.exec(select(ExchangeRate)).one()

    assert rate.date == SEPT_15
    assert rate.usd_to_cad == Decimal("1.3845")
    assert isinstance(rate.usd_to_cad, Decimal)


def test_saving_same_day_again_replaces_the_rate(session: Session):
    save_exchange_rate(session, SEPT_15, Decimal("1.3845"))
    save_exchange_rate(session, SEPT_15, Decimal("1.3900"))

    rates = session.exec(select(ExchangeRate)).all()

    assert len(rates) == 1
    assert rates[0].usd_to_cad == Decimal("1.3900")


# --- GET /exchange-rates ---


@pytest.fixture
def sample_rates(session: Session):
    """Rates for three business days (Fri, Mon, Tue) around a weekend."""
    for day, rate in [(11, "1.3801"), (14, "1.3822"), (15, "1.3845")]:
        save_exchange_rate(session, datetime.date(2026, 9, day), Decimal(rate))


def test_no_rates_stored_returns_empty_list(client: TestClient):
    response = client.get("/exchange-rates")

    assert response.status_code == 200
    assert response.json() == []


def test_lists_rates_oldest_first(client: TestClient, sample_rates):
    response = client.get("/exchange-rates")

    assert response.json() == [
        {"date": "2026-09-11", "usd_to_cad": "1.380100"},
        {"date": "2026-09-14", "usd_to_cad": "1.382200"},
        {"date": "2026-09-15", "usd_to_cad": "1.384500"},
    ]


def test_filter_by_date_range_includes_both_ends(client: TestClient, sample_rates):
    rates = client.get(
        "/exchange-rates", params={"start": "2026-09-12", "end": "2026-09-15"}
    ).json()

    assert [r["date"] for r in rates] == ["2026-09-14", "2026-09-15"]


def test_invalid_date_is_rejected(client: TestClient):
    response = client.get("/exchange-rates", params={"start": "yesterday"})

    assert response.status_code == 422
