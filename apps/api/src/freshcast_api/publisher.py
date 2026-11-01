"""Outbox publisher: forwards committed events to the event bus.

Delivery is at-least-once: an event is marked published only *after* the sink
accepted it. A crash in between causes a re-send, which consumers absorb through
event-id idempotency (see ``freshcast.events.processor``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from freshcast.events.contracts import ChangeType, ForecastChangeEvent
from freshcast_api.models import OutboxEvent


class EventSink(Protocol):
    """Destination such as EventBridge or SQS (adapter added in phase 7)."""

    def send(self, event: ForecastChangeEvent) -> None:
        """Deliver one event; raise on failure."""


def _to_contract(row: OutboxEvent) -> ForecastChangeEvent:
    store_id, _, sku = row.partition_key.partition(":")
    occurred = row.occurred_at
    if occurred.tzinfo is None:  # SQLite drops tz info; values are stored in UTC
        occurred = occurred.replace(tzinfo=UTC)
    return ForecastChangeEvent(
        event_id=row.event_id,
        event_type=ChangeType(row.event_type),
        store_id=store_id,
        sku=sku,
        occurred_at=occurred,
        entity_version=row.entity_version,
    )


def publish_pending(
    factory: sessionmaker[Session], sink: EventSink, limit: int = 100
) -> int:
    """Send unpublished events oldest-first; stop at the first failure.

    Stopping preserves per-partition order. Returns the number published.
    """
    published = 0
    with factory() as session:
        rows = session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.occurred_at, OutboxEvent.entity_version)
            .limit(limit)
        ).all()
        for row in rows:
            sink.send(_to_contract(row))
            row.published_at = datetime.now(UTC)
            session.commit()
            published += 1
    return published
