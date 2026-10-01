import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.models import Metal, MetalPrice
from app.prices import save_metal_price

SEPT_15 = datetime.date(2026, 9, 15)


def test_save_metal_price_stores_a_new_price(session: Session):
    save_metal_price(session, Metal.GOLD, SEPT_15, Decimal("2650.1234"))

    price = session.exec(select(MetalPrice)).one()

    assert price.metal == Metal.GOLD
    assert price.date == SEPT_15
    assert price.spot_price_usd == Decimal("2650.1234")
    assert isinstance(price.spot_price_usd, Decimal)


def test_saving_same_metal_and_day_again_replaces_the_price(session: Session):
    save_metal_price(session, Metal.GOLD, SEPT_15, Decimal("2650.00"))
    save_metal_price(session, Metal.GOLD, SEPT_15, Decimal("2675.50"))

    prices = session.exec(select(MetalPrice)).all()

    assert len(prices) == 1
    assert prices[0].spot_price_usd == Decimal("2675.50")


def test_different_metals_on_the_same_day_are_kept_separately(session: Session):
    save_metal_price(session, Metal.GOLD, SEPT_15, Decimal("2650.00"))
    save_metal_price(session, Metal.SILVER, SEPT_15, Decimal("31.25"))

    prices = session.exec(select(MetalPrice)).all()

    assert {p.metal for p in prices} == {Metal.GOLD, Metal.SILVER}
