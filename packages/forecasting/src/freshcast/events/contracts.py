"""Typed change-event contract for incremental recomputation.

This module only defines *what an event looks like*. Idempotency,
monotonic version checks and atomic writes are the worker's job and are
implemented separately (phase 6).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChangeType(StrEnum):
    """Business changes that can invalidate forecasts or proposals."""

    SALES_UPDATED = "sales.updated"
    PRICE_UPDATED = "price.updated"
    STOCK_UPDATED = "stock.updated"


class ForecastChangeEvent(BaseModel):
    """Immutable, strictly validated change event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    event_id: UUID  # idempotency key
    event_type: ChangeType
    store_id: str = Field(min_length=1, max_length=64)
    sku: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    entity_version: int = Field(ge=1)  # lets workers drop stale events

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject naive timestamps; all times must carry an offset."""
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


def affected_partition(event: ForecastChangeEvent) -> str:
    """Return the logical dependency key (not a storage path)."""
    return f"{event.store_id}:{event.sku}"
