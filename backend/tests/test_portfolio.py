"""Portfolio value tests, using small numbers that are easy to check by hand.

The scenario: 2 troy oz of gold bought on Friday 2026-09-11 for 8,000.00 USD.

    Date            Gold (USD/oz)   USD to CAD
    Fri 2026-09-11  4000            1.38
    Sat/Sun         (none)          (none)       -> use Friday's
    Mon 2026-09-14  4100            1.40
"""

import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.exchange_rates import save_exchange_rate
from app.models import Currency, Metal, Purchase
from app.portfolio import DailySeries, portfolio_history
from app.prices import save_metal_price
from app.units import WeightUnit

THU = datetime.date(2026, 9, 10)
FRI = datetime.date(2026, 9, 11)
SAT = datetime.date(2026, 9, 12)
MON = datetime.date(2026, 9, 14)


def buy(session: Session, metal: Metal, ounces: str, day: datetime.date, paid: str, currency: Currency):
    session.add(
        Purchase.from_entry(
            metal=metal,
            weight=Decimal(ounces),
            unit=WeightUnit.TROY_OUNCE,
            purchase_date=day,
            price_paid=Decimal(paid),
            currency=currency,
        )
    )
    session.commit()


@pytest.fixture
def market(session: Session):
    """Gold and silver prices and exchange rates for Friday and Monday."""
    save_metal_price(session, Metal.GOLD, FRI, Decimal("4000"))
    save_metal_price(session, Metal.GOLD, MON, Decimal("4100"))
    save_metal_price(session, Metal.SILVER, FRI, Decimal("48"))
    save_metal_price(session, Metal.SILVER, MON, Decimal("50"))
    save_exchange_rate(session, FRI, Decimal("1.38"))
    save_exchange_rate(session, MON, Decimal("1.40"))


@pytest.fixture
def gold_bought_friday(session: Session, market):
    buy(session, Metal.GOLD, "2", FRI, "8000.00", Currency.USD)


def day_of(session: Session, currency: Currency, day: datetime.date):
    [result] = portfolio_history(session, currency, day, day)
    return result


# --- "Latest value on or before a day" ---


def test_daily_series_uses_the_exact_day_when_available():
    series = DailySeries({FRI: Decimal("1"), MON: Decimal("2")})

    assert series.on_or_before(MON) == Decimal("2")


def test_daily_series_falls_back_to_the_most_recent_earlier_day():
    series = DailySeries({FRI: Decimal("1"), MON: Decimal("2")})

    assert series.on_or_before(SAT) == Decimal("1")


def test_daily_series_has_nothing_before_its_first_day():
    series = DailySeries({FRI: Decimal("1")})

    assert series.on_or_before(THU) is None


def test_daily_series_accepts_values_up_to_7_days_old_but_not_8():
    series = DailySeries({FRI: Decimal("1")})

    assert series.on_or_before(FRI + datetime.timedelta(days=7)) == Decimal("1")
    assert series.on_or_before(FRI + datetime.timedelta(days=8)) is None


# --- Value, cost and gain in USD ---


def test_value_on_the_purchase_day(session: Session, gold_bought_friday):
    day = day_of(session, Currency.USD, FRI)

    assert day.value == Decimal("8000.00")  # 2 oz x 4000
    assert day.cost == Decimal("8000.00")
    assert day.gain == Decimal("0.00")
    assert day.gain_percent == Decimal("0.00")


def test_weekend_uses_fridays_price(session: Session, gold_bought_friday):
    assert day_of(session, Currency.USD, SAT).value == Decimal("8000.00")


def test_gain_when_the_price_rises(session: Session, gold_bought_friday):
    day = day_of(session, Currency.USD, MON)

    assert day.value == Decimal("8200.00")  # 2 oz x 4100
    assert day.gain == Decimal("200.00")
    assert day.gain_percent == Decimal("2.50")  # 200 / 8000


def test_before_the_first_purchase_everything_is_zero(session: Session, gold_bought_friday):
    for currency in Currency:
        day = day_of(session, currency, THU)

        assert day.value == Decimal("0")
        assert day.cost == Decimal("0.00")
        assert day.gain == Decimal("0.00")
        assert day.gain_percent is None  # can't be a percentage of nothing


def test_several_metals_are_added_together(session: Session, gold_bought_friday):
    buy(session, Metal.SILVER, "100", MON, "5000.00", Currency.USD)

    day = day_of(session, Currency.USD, MON)

    assert day.value == Decimal("13200.00")  # 2 x 4100 + 100 x 50
    assert day.cost == Decimal("13000.00")
    assert day.gain_percent == Decimal("1.54")  # 200 / 13000 = 1.538...


# --- Converting to CAD ---


def test_value_in_cad_uses_that_days_rate(session: Session, gold_bought_friday):
    day = day_of(session, Currency.CAD, MON)

    assert day.value == Decimal("11480.00")  # 8200 USD x 1.40


def test_weekend_in_cad_uses_fridays_rate(session: Session, gold_bought_friday):
    assert day_of(session, Currency.CAD, SAT).value == Decimal("11040.00")  # 8000 x 1.38


def test_usd_purchase_cost_in_cad_uses_the_rate_on_the_purchase_date(
    session: Session, gold_bought_friday
):
    day = day_of(session, Currency.CAD, MON)

    # Paid 8000 USD on Friday when 1 USD = 1.38 CAD. Monday's rate doesn't change the cost.
    assert day.cost == Decimal("11040.00")
    assert day.gain == Decimal("440.00")  # 11480 - 11040
    assert day.gain_percent == Decimal("3.99")  # 440 / 11040 = 3.985...


def test_cad_purchase_cost_in_usd_uses_the_rate_on_the_purchase_date(
    session: Session, market
):
    buy(session, Metal.SILVER, "100", MON, "7000.00", Currency.CAD)

    day = day_of(session, Currency.USD, MON)

    assert day.cost == Decimal("5000.00")  # 7000 CAD / 1.40
    assert day.value == Decimal("5000.00")  # 100 oz x 50


def test_cad_purchase_shown_in_cad_is_not_converted(session: Session, market):
    buy(session, Metal.SILVER, "100", MON, "7000.00", Currency.CAD)

    assert day_of(session, Currency.CAD, MON).cost == Decimal("7000.00")


# --- Missing data ---


def test_value_is_unknown_without_any_price_yet(session: Session):
    buy(session, Metal.GOLD, "2", FRI, "8000.00", Currency.USD)

    day = day_of(session, Currency.USD, FRI)

    assert day.value is None
    assert day.cost == Decimal("8000.00")
    assert day.gain is None
    assert day.gain_percent is None


def test_value_is_unknown_when_prices_are_more_than_7_days_old(session: Session, gold_bought_friday):
    assert day_of(session, Currency.USD, MON + datetime.timedelta(days=7)).value is not None
    assert day_of(session, Currency.USD, MON + datetime.timedelta(days=8)).value is None


def test_cad_value_is_unknown_without_an_exchange_rate(session: Session):
    save_metal_price(session, Metal.GOLD, FRI, Decimal("4000"))
    buy(session, Metal.GOLD, "2", FRI, "8000.00", Currency.USD)

    day = day_of(session, Currency.CAD, FRI)

    assert day.value is None
    assert day.cost is None


def test_history_has_one_entry_per_day(session: Session, gold_bought_friday):
    history = portfolio_history(session, Currency.USD, THU, MON)

    assert [d.date for d in history] == [THU, FRI, SAT, SAT + datetime.timedelta(days=1), MON]


# --- GET /portfolio/history ---


def test_endpoint_returns_daily_values_as_exact_strings(client: TestClient, gold_bought_friday):
    response = client.get(
        "/portfolio/history", params={"currency": "CAD", "start": "2026-09-14", "end": "2026-09-14"}
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "date": "2026-09-14",
            "value": "11480.00",
            "cost": "11040.00",
            "gain": "440.00",
            "gain_percent": "3.99",
        }
    ]


def test_endpoint_defaults_to_cad_from_first_purchase_to_today(client: TestClient, gold_bought_friday):
    history = client.get("/portfolio/history").json()

    assert history[0]["date"] == "2026-09-11"
    assert history[0]["value"] == "11040.00"  # CAD
    assert history[-1]["date"] == datetime.date.today().isoformat()


def test_endpoint_returns_empty_list_with_no_purchases(client: TestClient):
    assert client.get("/portfolio/history").json() == []


def test_endpoint_shows_unknown_values_as_null(client: TestClient, session: Session):
    buy(session, Metal.GOLD, "2", FRI, "8000.00", Currency.USD)

    [day] = client.get(
        "/portfolio/history", params={"currency": "USD", "start": "2026-09-11", "end": "2026-09-11"}
    ).json()

    assert day["value"] is None
    assert day["gain"] is None


def test_endpoint_rejects_start_after_end(client: TestClient):
    response = client.get("/portfolio/history", params={"start": "2026-09-14", "end": "2026-09-11"})

    assert response.status_code == 422


def test_endpoint_rejects_unknown_currency(client: TestClient):
    response = client.get("/portfolio/history", params={"currency": "EUR"})

    assert response.status_code == 422
