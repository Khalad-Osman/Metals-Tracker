import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import ExchangeRate
from app.schemas import ExchangeRateRead

router = APIRouter(prefix="/exchange-rates", tags=["exchange rates"])


@router.get("", response_model=list[ExchangeRateRead])
def list_exchange_rates(
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    session: Session = Depends(get_session),
):
    """Stored USD to CAD rates, oldest first. Optionally filter by date range (inclusive).

    The Bank of Canada only publishes on business days, so weekends and holidays have no rate.
    """
    statement = select(ExchangeRate)
    if start is not None:
        statement = statement.where(ExchangeRate.date >= start)
    if end is not None:
        statement = statement.where(ExchangeRate.date <= end)
    return session.exec(statement.order_by(ExchangeRate.date)).all()
