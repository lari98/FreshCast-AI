"""Replenishment proposal endpoints (human-in-the-loop)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from freshcast.assistant.facts import ExplanationFacts
from freshcast.assistant.prompt import Language
from freshcast.assistant.service import explain
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
from freshcast_api.schemas import ExplanationOut, ProposalIn, ProposalOut
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


_DISCLAIMER = {
    "model": "AI-generated text. Every number was checked against system data. "
    "A store manager must approve the proposal.",
    "template": "Standard text generated from system data without AI. "
    "A store manager must approve the proposal.",
}


@router.get("/{proposal_id}/explanation", response_model=ExplanationOut)
def explain_proposal(
    proposal_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    who: AnyUser,
    lang: Annotated[Language, Query()] = "en",
) -> ExplanationOut:
    """Explain a proposal in German or English from stored facts only."""
    proposal = _get_or_404(session, proposal_id)
    inputs = proposal.inputs
    as_of = date.fromisoformat(str(inputs["as_of_date"]))
    lead = int(str(inputs["supplier_lead_days"]))
    facts = ExplanationFacts(
        store_id=proposal.store_id,
        sku=proposal.sku,
        product_name=proposal.sku,  # no product catalogue yet
        as_of_date=as_of,
        arrival_date=as_of + timedelta(days=lead),
        forecast_units=int(str(inputs["forecast_units"])),
        safety_stock_units=int(str(inputs["safety_stock_units"])),
        incoming_units=int(str(inputs["incoming_units"])),
        usable_stock_units=proposal.usable_stock_units,
        expiring_stock_units=proposal.expiring_stock_units,
        blocked_units=0,  # holds are not stored in the database yet
        target_stock_units=proposal.target_stock_units,
        recommended_order_units=proposal.recommended_order_units,
        order_multiple=int(str(inputs["order_multiple"])),
        supplier_lead_days=lead,
    )
    result = explain(facts, lang, request.app.state.text_model)
    audit(
        session,
        who,
        f"proposal.explain.{result.source}",
        "order_proposal",
        str(proposal.id),
    )
    session.commit()
    return ExplanationOut(
        text=result.text,
        language=result.language,
        source=result.source,
        ai_generated=result.ai_generated,
        violations=list(result.violations),
        prompt_version=result.prompt_version,
        disclaimer=_DISCLAIMER[result.source],
    )
