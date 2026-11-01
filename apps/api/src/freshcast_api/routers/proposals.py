"""Replenishment proposal endpoints (human-in-the-loop)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from freshcast.replenishment.engine import (
    ReplenishmentRequest,
    calculate_replenishment,
)
from freshcast.replenishment.engine import (
    StockLot as DomainLot,
)
from freshcast_api.deps import SessionDep
from freshcast_api.models import OrderProposal, StockLot
from freshcast_api.outbox import audit
from freshcast_api.schemas import ProposalIn, ProposalOut
from freshcast_api.security import Principal, Role, require_role

router = APIRouter(prefix="/v1/proposals", tags=["replenishment"])

Manager = Annotated[Principal, Depends(require_role(Role.STORE_MANAGER, Role.ADMIN))]
AnyUser = Annotated[Principal, Depends(require_role(*Role))]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProposalOut)
def create_proposal(
    body: ProposalIn, session: SessionDep, who: Manager
) -> OrderProposal:
    """Compute a proposal from forecast inputs and current stock lots."""
    lots = session.scalars(
        select(StockLot).where(
            StockLot.store_id == body.store_id, StockLot.sku == body.sku
        )
    ).all()
    request = ReplenishmentRequest(
        **body.model_dump(),
        stock_lots=tuple(
            DomainLot(lot.lot_id, lot.quantity, lot.use_by_date) for lot in lots
        ),
    )
    decision = calculate_replenishment(request)
    proposal = OrderProposal(
        store_id=body.store_id,
        sku=body.sku,
        inputs=body.model_dump(mode="json"),
        usable_stock_units=decision.usable_stock_units,
        expiring_stock_units=decision.expiring_stock_units,
        target_stock_units=decision.target_stock_units,
        recommended_order_units=decision.recommended_order_units,
        created_by=who.user,
    )
    session.add(proposal)
    session.flush()
    audit(session, who, "proposal.create", "order_proposal", str(proposal.id))
    session.commit()
    return proposal


def _get_or_404(session: SessionDep, proposal_id: uuid.UUID) -> OrderProposal:
    proposal = session.get(OrderProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return proposal


@router.get("/{proposal_id}", response_model=ProposalOut)
def read_proposal(
    proposal_id: uuid.UUID, session: SessionDep, who: AnyUser
) -> OrderProposal:
    """Return one proposal."""
    del who  # authorisation is enforced by the dependency
    return _get_or_404(session, proposal_id)


@router.post("/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(
    proposal_id: uuid.UUID, session: SessionDep, who: Manager
) -> OrderProposal:
    """Approve a pending proposal; the approver must differ from the creator."""
    proposal = _get_or_404(session, proposal_id)
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Proposal is not pending")
    if proposal.created_by == who.user:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Four-eyes rule: creator cannot approve"
        )
    proposal.status = "approved"
    proposal.approved_by = who.user
    proposal.approved_at = datetime.now(UTC)
    audit(session, who, "proposal.approve", "order_proposal", str(proposal.id))
    session.commit()
    return proposal
