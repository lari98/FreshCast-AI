"""In-memory ports for tests and local demos (not for production)."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from freshcast.events.contracts import ForecastChangeEvent


class InMemoryStateStore:
    """Thread-safe ledger; production uses PostgreSQL with one transaction."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._lock = threading.Lock()
        self._seen: set[UUID] = set()
        self._versions: dict[str, int] = {}

    def seen(self, event_id: UUID) -> bool:
        """Return True if the id was committed."""
        with self._lock:
            return event_id in self._seen

    def latest_version(self, partition: str) -> int:
        """Return the committed version (0 if none)."""
        with self._lock:
            return self._versions.get(partition, 0)

    def commit(self, event_ids: Sequence[UUID], partition: str, version: int) -> None:
        """Mark ids seen and raise the version monotonically."""
        with self._lock:
            self._seen.update(event_ids)
            self._versions[partition] = max(self._versions.get(partition, 0), version)


@dataclass(frozen=True, slots=True)
class DeadLetter:
    """A failed event with its error."""

    event: ForecastChangeEvent
    error: str
    attempts: int


class InMemoryDeadLetterQueue:
    """Collects dead letters; ``drain`` hands them back for replay."""

    def __init__(self) -> None:
        """Create an empty queue."""
        self.items: list[DeadLetter] = []

    def put(self, event: ForecastChangeEvent, error: str, attempts: int) -> None:
        """Store a failed event."""
        self.items.append(DeadLetter(event, error, attempts))

    def drain(self) -> list[ForecastChangeEvent]:
        """Remove and return all events for replay."""
        events = [item.event for item in self.items]
        self.items.clear()
        return events
