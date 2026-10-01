import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.models import Metal, MetalPrice


def save_metal_price(
    session: Session, metal: Metal, date: datetime.date, spot_price_usd: Decimal
) -> MetalPrice:
    """Store a metal's spot price for a day, replacing any price already stored for it."""
    price = session.exec(
        select(MetalPrice).where(MetalPrice.metal == metal, MetalPrice.date == date)
    ).first()

    if price is None:
        price = MetalPrice(metal=metal, date=date, spot_price_usd=spot_price_usd)
    else:
        price.spot_price_usd = spot_price_usd

    session.add(price)
    session.commit()
    session.refresh(price)
    return price
