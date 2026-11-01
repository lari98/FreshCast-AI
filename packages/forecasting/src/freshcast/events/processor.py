"""Incremental event processing: recompute only what a change affects.

Guarantees (see docs/architecture/events.md)
--------------------------------------------
* Idempotent: a delivered-twice event causes one recomputation.
* Stale-safe: an event whose ``entity_version`` is not newer than the
  partition's committed version is dropped without recomputing.
* Targeted: only the stages a change type affects run, and only for the
  event's ``store:sku`` partition.
* Coalescing: a batch of events for one partition triggers one run covering
  the union of stages, committed at the highest version.
* Recoverable: after bounded retries a failing event goes to a dead-letter
  queue *without* being marked processed, so it can be replayed.

Stages recompute from the *current* database state, never from the event
payload. That is why dropping stale events and coalescing are safe: the latest
run already reflects every earlier change.

Deployment note: consume from SQS FIFO with ``MessageGroupId = partition key``
so one partition is never processed by two workers at once.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from freshcast.events.contracts import (
    ChangeType,
    ForecastChangeEvent,
    affected_partition,
)

logger = logging.getLogger(__name__)


class Stage(StrEnum):
    """Recomputation stages, declared in dependency order."""

    FEATURES = "features"
    FORECAST = "forecast"
    PROPOSAL = "proposal"


_ORDER = list(Stage)

# What each change invalidates (mirrors the blueprint's trigger table).
STAGES_BY_CHANGE: dict[ChangeType, tuple[Stage, ...]] = {
    ChangeType.SALES_UPDATED: (Stage.FEATURES, Stage.FORECAST, Stage.PROPOSAL),
    ChangeType.PRICE_UPDATED: (Stage.FEATURES, Stage.FORECAST, Stage.PROPOSAL),
    ChangeType.STOCK_UPDATED: (Stage.PROPOSAL,),  # no model or feature change
}


class Outcome(StrEnum):
    """What happened to one event."""

    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    STALE = "stale"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True, slots=True)
class HandleResult:
    """Per-event result, useful for metrics and tests."""

    event_id: UUID
    outcome: Outcome
    stages: tuple[Stage, ...] = ()


class Recomputer(Protocol):
    """Recompute one stage for one partition from current state."""

    def __call__(self, partition: str, stage: Stage) -> None:
        """Run the stage; raise on failure."""


class StateStore(Protocol):
    """Idempotency ledger plus per-partition version, updated atomically."""

    def seen(self, event_id: UUID) -> bool:
        """Return True if the event id was already committed."""

    def latest_version(self, partition: str) -> int:
        """Return the committed version (0 if none)."""

    def commit(self, event_ids: Sequence[UUID], partition: str, version: int) -> None:
        """Atomically mark ids seen and raise the version to at least ``version``."""


class DeadLetterSink(Protocol):
    """Destination for events that exhausted their retries."""

    def put(self, event: ForecastChangeEvent, error: str, attempts: int) -> None:
        """Store the failed event for inspection and replay."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retries with exponential backoff."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        """Validate bounds."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative")


class EventProcessor:
    """Apply change events to the recomputation stages."""

    def __init__(
        self,
        store: StateStore,
        recompute: Recomputer,
        dead_letters: DeadLetterSink,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Wire the ports; ``sleep`` is injectable so tests run instantly."""
        self._store = store
        self._recompute = recompute
        self._dead_letters = dead_letters
        self._retry = retry or RetryPolicy()
        self._sleep = sleep

    def handle(self, event: ForecastChangeEvent) -> HandleResult:
        """Process a single event."""
        return self.process_batch([event])[0]

    def process_batch(
        self, events: Sequence[ForecastChangeEvent]
    ) -> list[HandleResult]:
        """Process events, coalescing per partition; results keep input order."""
        results: list[HandleResult | None] = [None] * len(events)
        fresh: dict[str, list[tuple[int, ForecastChangeEvent]]] = defaultdict(list)
        seen_in_batch: set[UUID] = set()

        for index, event in enumerate(events):
            partition = affected_partition(event)
            eid = event.event_id
            if eid in seen_in_batch or self._store.seen(eid):
                results[index] = HandleResult(eid, Outcome.DUPLICATE)
            elif event.entity_version <= self._store.latest_version(partition):
                # Newer state already computed; remember the id and move on.
                self._store.commit([eid], partition, event.entity_version)
                results[index] = HandleResult(eid, Outcome.STALE)
            else:
                fresh[partition].append((index, event))
            seen_in_batch.add(eid)

        for partition, items in fresh.items():
            outcomes = self._run_partition(partition, [e for _, e in items])
            for (index, _), result in zip(items, outcomes, strict=True):
                results[index] = result
        return [r for r in results if r is not None]

    def _run_partition(
        self, partition: str, fresh: list[ForecastChangeEvent]
    ) -> list[HandleResult]:
        wanted = {s for e in fresh for s in STAGES_BY_CHANGE[e.event_type]}
        stages = tuple(s for s in _ORDER if s in wanted)
        try:
            for stage in stages:
                self._run_stage(partition, stage)
        except _StageFailed as failure:
            for event in fresh:
                self._dead_letters.put(event, failure.error, failure.attempts)
            logger.error(
                "partition dead-lettered",
                extra={"partition": partition, "stage": failure.stage.value},
            )
            return [HandleResult(e.event_id, Outcome.DEAD_LETTERED) for e in fresh]
        # Commit only after every stage succeeded: failures stay replayable.
        self._store.commit(
            [e.event_id for e in fresh], partition, max(e.entity_version for e in fresh)
        )
        return [HandleResult(e.event_id, Outcome.PROCESSED, stages) for e in fresh]

    def _run_stage(self, partition: str, stage: Stage) -> None:
        last_error = ""
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                self._recompute(partition, stage)
            except Exception as exc:  # noqa: BLE001 - any stage failure is retried
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self._retry.max_attempts:
                    self._sleep(self._retry.base_delay_seconds * 2 ** (attempt - 1))
            else:
                return
        raise _StageFailed(stage, last_error, self._retry.max_attempts)


class _StageFailed(Exception):
    """Internal: a stage exhausted its retries."""

    def __init__(self, stage: Stage, error: str, attempts: int) -> None:
        super().__init__(error)
        self.stage, self.error, self.attempts = stage, error, attempts
