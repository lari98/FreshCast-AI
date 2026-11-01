"""Request and response contracts with strict validation."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=64)]


class StockLotIn(BaseModel):
    """Inventory lot received at a store."""

    model_config = ConfigDict(extra="forbid")

    store_id: Identifier
    sku: Identifier
    lot_id: Identifier
    quantity: int = Field(ge=0, le=1_000_000)
    use_by_date: date


class StockLotOut(BaseModel):
    """Stored lot plus the event version it produced."""

    lot_id: str
    entity_version: int


class ProposalIn(BaseModel):
    """Inputs for an order proposal; stock lots are read from the database."""

    model_config = ConfigDict(extra="forbid")

    store_id: Identifier
    sku: Identifier
    as_of_date: date
    forecast_units: int = Field(ge=0, le=1_000_000)
    safety_stock_units: int = Field(ge=0, le=1_000_000)
    incoming_units: int = Field(ge=0, le=1_000_000)
    supplier_lead_days: int = Field(ge=0, le=60)
    order_multiple: int = Field(ge=1, le=100_000)


class ProposalOut(BaseModel):
    """Order proposal returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: str
    sku: str
    usable_stock_units: int
    expiring_stock_units: int
    target_stock_units: int
    recommended_order_units: int
    status: str
    created_by: str
    approved_by: str | None
