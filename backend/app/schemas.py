from datetime import date
from decimal import Decimal

from pydantic import field_serializer, field_validator
from sqlmodel import Field, SQLModel

from app.models import Currency, Metal
from app.units import WeightUnit


class PurchaseCreate(SQLModel):
    """What the client sends to log a new purchase."""

    metal: Metal
    weight: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    unit: WeightUnit
    purchase_date: date
    price_paid: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency

    @field_validator("purchase_date")
    @classmethod
    def not_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("purchase date can't be in the future")
        return value


class PurchaseRead(SQLModel):
    """What the API sends back for a purchase."""

    id: int
    metal: Metal
    weight_oz: Decimal
    original_weight: Decimal
    original_unit: WeightUnit
    purchase_date: date
    price_paid: Decimal
    currency: Currency

    @field_serializer("original_weight")
    def without_trailing_zeros(self, value: Decimal) -> str:
        # The database pads to 6 decimal places; show "100" rather than "100.000000".
        return format(value.normalize(), "f")
