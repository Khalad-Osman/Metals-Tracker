from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.models import Currency, Metal, Purchase
from app.units import WeightUnit


def make_gram_purchase() -> Purchase:
    return Purchase.from_entry(
        metal=Metal.GOLD,
        weight=Decimal("100"),
        unit=WeightUnit.GRAM,
        purchase_date=date(2026, 9, 15),
        price_paid=Decimal("14250.75"),
        currency=Currency.CAD,
    )


def test_from_entry_converts_weight_and_keeps_original():
    purchase = make_gram_purchase()

    assert purchase.weight_oz == Decimal("3.21507466")
    assert purchase.original_weight == Decimal("100")
    assert purchase.original_unit == WeightUnit.GRAM


def test_purchase_is_saved_and_loaded_unchanged(session: Session):
    session.add(make_gram_purchase())
    session.commit()

    loaded = session.exec(select(Purchase)).one()

    assert loaded.id is not None
    assert loaded.metal == Metal.GOLD
    assert loaded.weight_oz == Decimal("3.21507466")
    assert loaded.original_weight == Decimal("100")
    assert loaded.original_unit == WeightUnit.GRAM
    assert loaded.purchase_date == date(2026, 9, 15)
    assert loaded.price_paid == Decimal("14250.75")
    assert loaded.currency == Currency.CAD


def test_weights_and_money_come_back_as_decimal_not_float(session: Session):
    session.add(make_gram_purchase())
    session.commit()

    loaded = session.exec(select(Purchase)).one()

    assert isinstance(loaded.weight_oz, Decimal)
    assert isinstance(loaded.original_weight, Decimal)
    assert isinstance(loaded.price_paid, Decimal)
