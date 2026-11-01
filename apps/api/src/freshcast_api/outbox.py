"""Transactional outbox, versioning and audit helpers.

All helpers only add rows to the caller's session; the caller commits once,
so a business change, its event and its audit entry succeed or fail together.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from freshcast.events.contracts import ChangeType, partition_key
from freshcast_api.models import AuditLog, EntityVersion, OutboxEvent
from freshcast_api.security import Principal


def next_version(session: Session, partition_key: str) -> int:
    """Increment and return the monotonic version for a store:sku partition."""
    row = session.scalar(
        select(EntityVersion)
        .where(EntityVersion.partition_key == partition_key)
        .with_for_update()
    )
    if row is None:
        row = EntityVersion(partition_key=partition_key, version=0)
        session.add(row)
    row.version += 1
    return row.version


def add_event(
    session: Session,
    event_type: ChangeType,
    store_id: str,
    sku: str,
    payload: dict[str, object],
) -> OutboxEvent:
    """Stage a change event for later publication to EventBridge/SQS."""
    key = partition_key(store_id, sku)
    event = OutboxEvent(
        event_type=event_type.value,
        partition_key=key,
        entity_version=next_version(session, key),
        payload=payload,
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    return event


def audit(
    session: Session, who: Principal, action: str, entity: str, entity_id: str
) -> None:
    """Append an audit entry."""
    session.add(
        AuditLog(
            actor=who.user,
            role=who.role.value,
            action=action,
            entity=entity,
            entity_id=entity_id,
        )
    )
