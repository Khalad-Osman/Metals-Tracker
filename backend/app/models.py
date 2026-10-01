import datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.units import WeightUnit, to_troy_ounces


class Metal(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    PLATINUM = "platinum"
    PALLADIUM = "palladium"


class Currency(str, Enum):
    CAD = "CAD"
    USD = "USD"


class Purchase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    metal: Metal
    # Weight in troy ounces, used for all calculations.
    weight_oz: Decimal = Field(max_digits=14, decimal_places=8)
    # What the user actually typed, so the purchase history can show it.
    original_weight: Decimal = Field(max_digits=14, decimal_places=6)
    original_unit: WeightUnit
    purchase_date: datetime.date
    # Total price paid, in the purchase's own currency.
    price_paid: Decimal = Field(max_digits=12, decimal_places=2)
    currency: Currency

    @classmethod
    def from_entry(
        cls,
        metal: Metal,
        weight: Decimal,
        unit: WeightUnit,
        purchase_date: datetime.date,
        price_paid: Decimal,
        currency: Currency,
    ) -> "Purchase":
        """Build a Purchase from what the user entered, filling in weight_oz."""
        return cls(
            metal=metal,
            weight_oz=to_troy_ounces(weight, unit),
            original_weight=weight,
            original_unit=unit,
            purchase_date=purchase_date,
            price_paid=price_paid,
            currency=currency,
        )


class MetalPrice(SQLModel, table=True):
    """The spot price of one metal on one day, in USD per troy ounce."""

    # Only one price per metal per day.
    __table_args__ = (UniqueConstraint("metal", "date"),)

    id: int | None = Field(default=None, primary_key=True)
    metal: Metal
    date: datetime.date
    spot_price_usd: Decimal = Field(max_digits=12, decimal_places=4)
