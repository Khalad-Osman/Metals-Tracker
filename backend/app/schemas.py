import datetime
from decimal import Decimal

from pydantic import field_serializer, field_validator
from sqlmodel import Field, SQLModel

from app.models import Currency, Metal
from app.units import WeightUnit


class PurchaseInput(SQLModel):
    """What the client sends to create or edit a purchase."""

    metal: Metal
    weight: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    unit: WeightUnit
    purchase_date: datetime.date
    price_paid: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency

    @field_validator("purchase_date")
    @classmethod
    def not_in_the_future(cls, value: datetime.date) -> datetime.date:
        if value > datetime.date.today():
            raise ValueError("purchase date can't be in the future")
        return value


class PurchaseRead(SQLModel):
    """What the API sends back for a purchase."""

    id: int
    metal: Metal
    weight_oz: Decimal
    original_weight: Decimal
    original_unit: WeightUnit
    purchase_date: datetime.date
    price_paid: Decimal
    currency: Currency

    @field_serializer("original_weight")
    def without_trailing_zeros(self, value: Decimal) -> str:
        # The database pads to 6 decimal places; show "100" rather than "100.000000".
        return format(value.normalize(), "f")


class MetalPriceRead(SQLModel):
    """A metal's spot price on one day, in USD per troy ounce."""

    metal: Metal
    date: datetime.date
    spot_price_usd: Decimal


class ExchangeRateRead(SQLModel):
    """How many Canadian dollars one US dollar bought on a day."""

    date: datetime.date
    usd_to_cad: Decimal


class PortfolioDayRead(SQLModel):
    """The portfolio on one day, in the requested currency.

    Amounts are None when there's no recent enough price or exchange rate to
    work them out. gain_percent is None before the first purchase.
    """

    date: datetime.date
    value: Decimal | None
    cost: Decimal | None
    gain: Decimal | None
    gain_percent: Decimal | None


class HoldingRead(SQLModel):
    """One metal's position on a day, in the requested currency.

    Amounts are None when there's no recent enough price or exchange rate.
    share_percent is this metal's part of the whole portfolio's value.
    """

    metal: Metal
    weight_oz: Decimal
    value: Decimal | None
    cost: Decimal | None
    gain: Decimal | None
    gain_percent: Decimal | None
    share_percent: Decimal | None
