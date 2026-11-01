"""ORM models. Business writes and outbox events share one transaction."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from freshcast_api.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class StockLot(Base):
    """Traceable inventory lot (EC 178/2002 lot identification)."""

    __tablename__ = "stock_lots"
    __table_args__ = (UniqueConstraint("store_id", "lot_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    lot_id: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    use_by_date: Mapped[date] = mapped_column(Date)


class EntityVersion(Base):
    """Monotonic per store:sku counter so consumers can drop stale events."""

    __tablename__ = "entity_versions"

    partition_key: Mapped[str] = mapped_column(String(130), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class OutboxEvent(Base):
    """Event committed atomically with the business change (outbox pattern)."""

    __tablename__ = "outbox_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64))
    partition_key: Mapped[str] = mapped_column(String(130), index=True)
    entity_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrderProposal(Base):
    """Order proposal; never an order. A human must approve it."""

    __tablename__ = "order_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    inputs: Mapped[dict[str, object]] = mapped_column(JSON)
    usable_stock_units: Mapped[int] = mapped_column(Integer)
    expiring_stock_units: Mapped[int] = mapped_column(Integer)
    target_stock_units: Mapped[int] = mapped_column(Integer)
    recommended_order_units: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(Base):
    """Append-only record of who did what (accountability, AI Act oversight)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actor: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))


class ProcessedEvent(Base):
    """Consumer-side idempotency ledger: ids of events already applied."""

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )


class PartitionState(Base):
    """Highest event version fully applied per store:sku partition."""

    __tablename__ = "partition_state"

    partition_key: Mapped[str] = mapped_column(String(130), primary_key=True)
    committed_version: Mapped[int] = mapped_column(Integer, default=0)
