from datetime import date
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel

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
    purchase_date: date
    # Total price paid, in the purchase's own currency.
    price_paid: Decimal = Field(max_digits=12, decimal_places=2)
    currency: Currency

    @classmethod
    def from_entry(
        cls,
        metal: Metal,
        weight: Decimal,
        unit: WeightUnit,
        purchase_date: date,
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
