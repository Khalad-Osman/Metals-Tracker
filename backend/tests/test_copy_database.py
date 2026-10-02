import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.copy_database import CopyError, copy_database
from app.exchange_rates import save_exchange_rate
from app.models import Currency, ExchangeRate, Metal, MetalPrice, Purchase
from app.prices import save_metal_price
from app.units import WeightUnit

DAY = datetime.date(2026, 9, 15)


@pytest.fixture
def source(tmp_path: Path):
    """A SQLite database with two purchases, a price and a rate."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'source.db').as_posix()}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for metal, grams in [(Metal.GOLD, "10"), (Metal.SILVER, "500")]:
            session.add(
                Purchase.from_entry(
                    metal=metal,
                    weight=Decimal(grams),
                    unit=WeightUnit.GRAM,
                    purchase_date=DAY,
                    price_paid=Decimal("1970.00"),
                    currency=Currency.CAD,
                )
            )
        session.commit()
        save_metal_price(session, Metal.GOLD, DAY, Decimal("4150.1234"))
        save_exchange_rate(session, DAY, Decimal("1.4188"))
    yield engine
    engine.dispose()


@pytest.fixture
def target(session: Session):
    """The test database (empty SQLite, or TEST_DATABASE_URL if set)."""
    return session.get_bind()


def test_copies_every_row_unchanged(source, target):
    copied = copy_database(source, target)

    assert copied == {"purchase": 2, "metalprice": 1, "exchangerate": 1}
    with Session(target) as session:
        gold = session.get(Purchase, 1)
        assert gold.metal == Metal.GOLD
        assert gold.weight_oz == Decimal("0.32150747")
        assert gold.original_weight == Decimal("10")
        assert gold.price_paid == Decimal("1970.00")
        assert session.exec(select(MetalPrice)).one().spot_price_usd == Decimal("4150.1234")
        assert session.exec(select(ExchangeRate)).one().usd_to_cad == Decimal("1.4188")


def test_new_rows_after_a_copy_get_fresh_ids(source, target):
    copy_database(source, target)

    with Session(target) as session:
        new = Purchase.from_entry(
            metal=Metal.PLATINUM,
            weight=Decimal("1"),
            unit=WeightUnit.TROY_OUNCE,
            purchase_date=DAY,
            price_paid=Decimal("1700.00"),
            currency=Currency.USD,
        )
        session.add(new)
        session.commit()  # on PostgreSQL this fails if the id counter wasn't moved on

        assert new.id == 3


def test_refuses_to_copy_into_a_database_with_data(source, target):
    copy_database(source, target)

    with pytest.raises(CopyError, match="must be empty"):
        copy_database(source, target)
