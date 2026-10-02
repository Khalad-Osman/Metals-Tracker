"""Limits on purchases in the public sandbox demo, where anyone can make changes.

They keep a shared demo sensible: no absurd amounts that would wreck the chart,
no purchases from before the demo has prices, and a cap on how many there are.
Everything is reset every night anyway (see app/reset_demo.py).
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import MetalPrice, Purchase
from app.schemas import PurchaseInput
from app.units import WeightUnit, to_troy_ounces

MAX_WEIGHT_KG = Decimal(100)
MAX_WEIGHT_OZ = to_troy_ounces(MAX_WEIGHT_KG, WeightUnit.KILOGRAM)
MAX_PRICE = Decimal(1_000_000)
MAX_PURCHASES = 50


def check_sandbox_limits(session: Session, entry: PurchaseInput, is_new: bool) -> None:
    """Raise an HTTP error if this purchase isn't allowed in the sandbox demo."""
    if is_new:
        count = session.exec(select(func.count()).select_from(Purchase)).one()
        if count >= MAX_PURCHASES:
            raise HTTPException(
                status_code=409,
                detail=f"The demo is full ({MAX_PURCHASES} purchases). It resets every night.",
            )

    # Reported like other validation errors, so the form shows them under each field.
    errors = []
    if to_troy_ounces(entry.weight, entry.unit) > MAX_WEIGHT_OZ:
        errors.append(("weight", f"The demo allows up to {MAX_WEIGHT_KG} kg"))
    if entry.price_paid > MAX_PRICE:
        errors.append(("price_paid", "The demo allows prices up to 1,000,000"))

    earliest_price = session.exec(
        select(func.min(MetalPrice.date)).where(MetalPrice.metal == entry.metal)
    ).one()
    if earliest_price is None or entry.purchase_date < earliest_price:
        since = earliest_price.isoformat() if earliest_price else "-"
        errors.append(("purchase_date", f"The demo only has prices from {since}"))

    if errors:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["body", field], "msg": message, "type": "sandbox_limit"}
                for field, message in errors
            ],
        )
