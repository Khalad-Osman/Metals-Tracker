import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.database import get_session
from app.models import Currency, Purchase
from app.portfolio import portfolio_history
from app.schemas import PortfolioDayRead

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/history", response_model=list[PortfolioDayRead])
def get_portfolio_history(
    currency: Currency = Currency.CAD,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    session: Session = Depends(get_session),
):
    """The portfolio's value, cost and gain for each day.

    Defaults to every day from the first purchase up to today.
    """
    if start is None:
        start = session.exec(select(func.min(Purchase.purchase_date))).one()
        if start is None:
            return []  # no purchases yet
    end = end or datetime.date.today()

    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")

    return portfolio_history(session, currency, start, end)
