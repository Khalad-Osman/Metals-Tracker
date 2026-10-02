from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app import config
from app.database import get_session
from app.models import Purchase
from app.schemas import PurchaseInput, PurchaseRead

router = APIRouter(prefix="/purchases", tags=["purchases"])


def block_in_demo_mode() -> None:
    """Refuse changes when this is the public read-only demo."""
    # Read at request time (not import time), so tests can switch demo mode on.
    if config.DEMO_MODE:
        raise HTTPException(
            status_code=403, detail="This is a read-only demo; purchases can't be changed."
        )


def get_purchase_or_404(purchase_id: int, session: Session) -> Purchase:
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.post(
    "", response_model=PurchaseRead, status_code=201, dependencies=[Depends(block_in_demo_mode)]
)
def create_purchase(entry: PurchaseInput, session: Session = Depends(get_session)):
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


@router.put(
    "/{purchase_id}", response_model=PurchaseRead, dependencies=[Depends(block_in_demo_mode)]
)
def update_purchase(
    purchase_id: int, entry: PurchaseInput, session: Session = Depends(get_session)
):
    """Replace a purchase's details with newly entered ones."""
    purchase = get_purchase_or_404(purchase_id, session)

    # Build the updated values the same way as a new purchase (so weight_oz is
    # recalculated), then copy them onto the existing row, keeping its id.
    updated = Purchase.from_entry(**entry.model_dump())
    purchase.sqlmodel_update(updated.model_dump(exclude={"id"}))

    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


@router.delete(
    "/{purchase_id}", status_code=204, dependencies=[Depends(block_in_demo_mode)]
)
def delete_purchase(purchase_id: int, session: Session = Depends(get_session)):
    purchase = get_purchase_or_404(purchase_id, session)
    session.delete(purchase)
    session.commit()
