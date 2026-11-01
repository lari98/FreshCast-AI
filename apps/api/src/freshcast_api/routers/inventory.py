"""Inventory endpoints: receiving stock lots."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from freshcast.events.contracts import ChangeType
from freshcast_api.deps import SessionDep
from freshcast_api.models import StockLot
from freshcast_api.outbox import add_event, audit
from freshcast_api.schemas import StockLotIn, StockLotOut
from freshcast_api.security import Principal, Role, require_role

router = APIRouter(prefix="/v1/stock-lots", tags=["inventory"])

Writer = Annotated[Principal, Depends(require_role(Role.STORE_MANAGER, Role.ADMIN))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StockLotOut)
def receive_lot(body: StockLotIn, session: SessionDep, who: Writer) -> StockLotOut:
    """Record a received lot and stage a ``stock.updated`` event atomically."""
    session.add(StockLot(**body.model_dump()))
    try:
        session.flush()  # surface the unique-constraint violation before eventing
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Lot already exists for this store"
        ) from None
    event = add_event(
        session,
        ChangeType.STOCK_UPDATED,
        body.store_id,
        body.sku,
        {"lot_id": body.lot_id, "quantity": body.quantity},
    )
    audit(session, who, "stock_lot.create", "stock_lot", body.lot_id)
    session.commit()
    return StockLotOut(lot_id=body.lot_id, entity_version=event.entity_version)
