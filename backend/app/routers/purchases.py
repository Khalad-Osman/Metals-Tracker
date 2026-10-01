from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Purchase
from app.schemas import PurchaseCreate, PurchaseRead

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseRead, status_code=201)
def create_purchase(entry: PurchaseCreate, session: Session = Depends(get_session)):
    purchase = Purchase.from_entry(**entry.model_dump())
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


@router.get("", response_model=list[PurchaseRead])
def list_purchases(session: Session = Depends(get_session)):
    """All purchases, newest first."""
    statement = select(Purchase).order_by(
        Purchase.purchase_date.desc(), Purchase.id.desc()
    )
    return session.exec(statement).all()
