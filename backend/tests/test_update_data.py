import datetime
from decimal import Decimal

import httpx2
from sqlmodel import Session, select

from app import price_fetcher, rate_fetcher
from app.exchange_rates import save_exchange_rate
from app.models import ExchangeRate, Metal, MetalPrice
from app.prices import save_metal_price
from app.update_data import update_all
from tests.test_price_fetcher import timeseries_response
from tests.test_rate_fetcher import EARLY_SEPTEMBER, valet_response

TODAY = datetime.date(2026, 9, 8)


def rate_client(handler=lambda request: valet_response(EARLY_SEPTEMBER)):
    return lambda: httpx2.Client(
        base_url=rate_fetcher.API_URL, transport=httpx2.MockTransport(handler)
    )


def price_client(handler=timeseries_response):
    return lambda: httpx2.Client(
        base_url=price_fetcher.API_URL, transport=httpx2.MockTransport(handler)
    )


def failing(request):
    raise httpx2.ConnectError("connection refused")


def test_updates_rates_and_prices(session: Session):
    messages, all_ok = update_all(session, TODAY, rate_client(), price_client())

    assert all_ok
    assert len(session.exec(select(ExchangeRate)).all()) == 5
    assert len(session.exec(select(MetalPrice)).all()) > 0
    assert messages[0].startswith("Exchange rates: saved 5")
    assert messages[1].startswith("Spot prices: saved")
    assert "1 API request(s)" in messages[1]


def test_prices_still_update_when_rates_fail(session: Session):
    messages, all_ok = update_all(session, TODAY, rate_client(failing), price_client())

    assert not all_ok
    assert "Exchange rates: FAILED" in messages[0]
    assert "Could not reach the Bank of Canada" in messages[0]
    assert messages[1].startswith("Spot prices: saved")
    assert len(session.exec(select(MetalPrice)).all()) > 0


def test_rates_still_update_when_prices_fail(session: Session):
    messages, all_ok = update_all(session, TODAY, rate_client(), price_client(failing))

    assert not all_ok
    assert messages[0].startswith("Exchange rates: saved")
    assert "Spot prices: FAILED" in messages[1]
    assert len(session.exec(select(ExchangeRate)).all()) == 5


def test_missing_api_key_is_reported_not_crashed(session: Session):
    def no_key():
        return price_fetcher.make_client("")

    messages, all_ok = update_all(session, TODAY, rate_client(), no_key)

    assert not all_ok
    assert "METALS_DEV_API_KEY is not set" in messages[1]


def test_reports_already_up_to_date(session: Session):
    tomorrow = TODAY + datetime.timedelta(days=1)
    save_exchange_rate(session, tomorrow, Decimal("1.4"))
    for metal in Metal:
        save_metal_price(session, metal, tomorrow, Decimal("100"))

    def must_not_be_called(request):
        raise AssertionError("no request should be made when up to date")

    messages, all_ok = update_all(
        session, TODAY, rate_client(must_not_be_called), price_client(must_not_be_called)
    )

    assert all_ok
    assert messages == [
        "Exchange rates: already up to date.",
        "Spot prices: already up to date.",
    ]
