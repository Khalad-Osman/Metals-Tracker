import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Metal, MetalPrice
from app.schemas import MetalPriceRead

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("", response_model=list[MetalPriceRead])
def list_prices(
    metal: Metal | None = None,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    session: Session = Depends(get_session),
):
    """Stored spot prices, oldest first. Optionally filter by metal and date range (inclusive)."""
    statement = select(MetalPrice)
    if metal is not None:
        statement = statement.where(MetalPrice.metal == metal)
    if start is not None:
        statement = statement.where(MetalPrice.date >= start)
    if end is not None:
        statement = statement.where(MetalPrice.date <= end)

    statement = statement.order_by(MetalPrice.date, MetalPrice.metal)
    return session.exec(statement).all()
