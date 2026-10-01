import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.database import get_session
from app.models import Currency, Purchase
from app.portfolio import holdings_on, portfolio_history
from app.schemas import HoldingRead, PortfolioDayRead

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


@router.get("/holdings", response_model=list[HoldingRead])
def get_holdings(
    currency: Currency = Currency.CAD,
    date: datetime.date | None = None,
    session: Session = Depends(get_session),
):
    """What's held of each metal, with its value, cost, gain and share. Defaults to today."""
    return holdings_on(session, currency, date or datetime.date.today())
