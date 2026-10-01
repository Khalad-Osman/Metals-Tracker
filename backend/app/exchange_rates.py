import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.models import ExchangeRate


def save_exchange_rate(
    session: Session, date: datetime.date, usd_to_cad: Decimal
) -> ExchangeRate:
    """Store the USD to CAD rate for a day, replacing any rate already stored for it."""
    rate = session.exec(select(ExchangeRate).where(ExchangeRate.date == date)).first()

    if rate is None:
        rate = ExchangeRate(date=date, usd_to_cad=usd_to_cad)
    else:
        rate.usd_to_cad = usd_to_cad

    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate
