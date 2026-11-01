"""PostgreSQL-backed ``StateStore`` for the event processor.

``commit`` records event ids and advances the partition version in ONE
transaction, so a crash can never leave "recomputed but not recorded" halves.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from freshcast_api.models import PartitionState, ProcessedEvent


class SqlStateStore:
    """Idempotency ledger and version tracker on a SQL database."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        """Use short-lived sessions from ``factory``."""
        self._factory = factory

    def seen(self, event_id: UUID) -> bool:
        """Return True if the event was already committed."""
        with self._factory() as session:
            return session.get(ProcessedEvent, event_id) is not None

    def latest_version(self, partition: str) -> int:
        """Return the committed version (0 if none)."""
        with self._factory() as session:
            state = session.get(PartitionState, partition)
            return state.committed_version if state else 0

    def commit(self, event_ids: Sequence[UUID], partition: str, version: int) -> None:
        """Atomically record ids and raise the version monotonically."""
        with self._factory() as session, session.begin():
            known = set(
                session.scalars(
                    select(ProcessedEvent.event_id).where(
                        ProcessedEvent.event_id.in_(list(event_ids))
                    )
                )
            )
            session.add_all(ProcessedEvent(event_id=i) for i in set(event_ids) - known)
            state = session.scalar(
                select(PartitionState)
                .where(PartitionState.partition_key == partition)
                .with_for_update()
            )
            if state is None:
                session.add(
                    PartitionState(partition_key=partition, committed_version=version)
                )
            else:
                state.committed_version = max(state.committed_version, version)
