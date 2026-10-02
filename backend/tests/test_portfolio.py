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
from app.portfolio import DailySeries, holdings_on, portfolio_history
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



# --- Holdings by metal ---


@pytest.fixture
def gold_and_silver(session: Session, gold_bought_friday):
    """2 oz gold (bought Friday for 8000 USD) and 100 oz silver (Monday, 5000 USD)."""
    buy(session, Metal.SILVER, "100", MON, "5000.00", Currency.USD)


def test_holdings_has_one_row_per_metal_in_metal_order(session: Session, gold_and_silver):
    holdings = holdings_on(session, Currency.USD, MON)

    assert [h.metal for h in holdings] == [Metal.GOLD, Metal.SILVER]


def test_holding_value_cost_and_gain(session: Session, gold_and_silver):
    gold, silver = holdings_on(session, Currency.USD, MON)

    assert gold.weight_oz == Decimal("2")
    assert gold.value == Decimal("8200.00")  # 2 x 4100
    assert gold.cost == Decimal("8000.00")
    assert gold.gain == Decimal("200.00")
    assert gold.gain_percent == Decimal("2.50")

    assert silver.value == Decimal("5000.00")  # 100 x 50
    assert silver.gain == Decimal("0.00")


def test_shares_of_the_portfolio_add_up_to_100(session: Session, gold_and_silver):
    gold, silver = holdings_on(session, Currency.USD, MON)

    assert gold.share_percent == Decimal("62.12")  # 8200 / 13200
    assert silver.share_percent == Decimal("37.88")  # 5000 / 13200
    assert gold.share_percent + silver.share_percent == Decimal("100.00")


def test_holdings_match_the_portfolio_total(session: Session, gold_and_silver):
    holdings = holdings_on(session, Currency.CAD, MON)
    total = day_of(session, Currency.CAD, MON)

    assert sum(h.value for h in holdings) == total.value
    assert sum(h.cost for h in holdings) == total.cost


def test_several_purchases_of_one_metal_are_combined(session: Session, gold_bought_friday):
    buy(session, Metal.GOLD, "1", MON, "4050.00", Currency.USD)

    [gold] = holdings_on(session, Currency.USD, MON)

    assert gold.weight_oz == Decimal("3")
    assert gold.value == Decimal("12300.00")  # 3 x 4100
    assert gold.cost == Decimal("12050.00")
    assert gold.gain_percent == Decimal("2.07")  # 250 / 12050 = 2.0747...
    assert gold.share_percent == Decimal("100.00")


def test_holdings_in_cad(session: Session, gold_bought_friday):
    [gold] = holdings_on(session, Currency.CAD, MON)

    assert gold.value == Decimal("11480.00")  # 8200 USD x 1.40 (Monday's rate)
    assert gold.cost == Decimal("11040.00")  # 8000 USD x 1.38 (rate on purchase day)


def test_metals_bought_later_are_not_included(session: Session, gold_and_silver):
    holdings = holdings_on(session, Currency.USD, FRI)

    assert [h.metal for h in holdings] == [Metal.GOLD]


def test_no_purchases_means_no_holdings(session: Session, market):
    assert holdings_on(session, Currency.USD, MON) == []


def test_unknown_value_leaves_shares_unknown(session: Session, gold_bought_friday):
    buy(session, Metal.PLATINUM, "1", MON, "1500.00", Currency.USD)  # no platinum prices

    gold, platinum = holdings_on(session, Currency.USD, MON)

    assert gold.value == Decimal("8200.00")
    assert platinum.value is None
    assert platinum.gain is None
    assert gold.share_percent is None  # can't be a share of an unknown total
    assert platinum.share_percent is None


def test_holdings_endpoint_returns_exact_strings(client: TestClient, gold_and_silver):
    response = client.get("/portfolio/holdings", params={"currency": "USD", "date": "2026-09-14"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "metal": "gold",
            "weight_oz": "2.00000000",
            "value": "8200.00",
            "cost": "8000.00",
            "gain": "200.00",
            "gain_percent": "2.50",
            "share_percent": "62.12",
        },
        {
            "metal": "silver",
            "weight_oz": "100.00000000",
            "value": "5000.00",
            "cost": "5000.00",
            "gain": "0.00",
            "gain_percent": "0.00",
            "share_percent": "37.88",
        },
    ]


def test_holdings_endpoint_defaults_to_today_in_cad(client: TestClient, session: Session):
    save_metal_price(session, Metal.GOLD, datetime.date.today(), Decimal("4000"))
    save_exchange_rate(session, datetime.date.today(), Decimal("1.5"))
    buy(session, Metal.GOLD, "1", datetime.date.today(), "6000.00", Currency.CAD)

    [gold] = client.get("/portfolio/holdings").json()

    assert gold["value"] == "6000.00"  # 1 oz x 4000 USD x 1.5


def test_holdings_endpoint_rejects_bad_input(client: TestClient):
    assert client.get("/portfolio/holdings", params={"currency": "EUR"}).status_code == 422
    assert client.get("/portfolio/holdings", params={"date": "soon"}).status_code == 422



# --- Filtering the history to one metal ---


def test_history_for_one_metal_counts_only_that_metal(session: Session, gold_and_silver):
    [gold] = portfolio_history(session, Currency.USD, MON, MON, metal=Metal.GOLD)
    [silver] = portfolio_history(session, Currency.USD, MON, MON, metal=Metal.SILVER)
    [everything] = portfolio_history(session, Currency.USD, MON, MON)

    assert (gold.value, gold.cost, gold.gain) == (
        Decimal("8200.00"),
        Decimal("8000.00"),
        Decimal("200.00"),
    )
    assert (silver.value, silver.cost) == (Decimal("5000.00"), Decimal("5000.00"))
    assert gold.value + silver.value == everything.value


def test_one_metal_is_zero_before_its_own_first_purchase(session: Session, gold_and_silver):
    [silver_on_friday] = portfolio_history(session, Currency.USD, FRI, FRI, metal=Metal.SILVER)

    assert silver_on_friday.value == Decimal("0")  # silver was only bought on Monday
    assert silver_on_friday.gain_percent is None


def test_endpoint_filters_by_metal_and_starts_at_its_first_purchase(
    client: TestClient, gold_and_silver
):
    history = client.get(
        "/portfolio/history", params={"currency": "USD", "metal": "silver", "end": "2026-09-14"}
    ).json()

    assert [d["date"] for d in history] == ["2026-09-14"]  # silver's first purchase
    assert history[0]["value"] == "5000.00"


def test_endpoint_returns_empty_list_for_a_metal_not_owned(client: TestClient, gold_and_silver):
    assert client.get("/portfolio/history", params={"metal": "platinum"}).json() == []


def test_endpoint_rejects_unknown_metal(client: TestClient):
    assert client.get("/portfolio/history", params={"metal": "copper"}).status_code == 422
