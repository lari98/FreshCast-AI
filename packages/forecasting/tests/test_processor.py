"""Incremental processing guarantees."""

import threading
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from freshcast.events.contracts import ChangeType, ForecastChangeEvent
from freshcast.events.memory import InMemoryDeadLetterQueue, InMemoryStateStore
from freshcast.events.processor import (
    EventProcessor,
    Outcome,
    RetryPolicy,
    Stage,
)


class Recorder:
    """Recomputer that records calls and can be told to fail."""

    def __init__(self) -> None:
        """Start with no calls and no scripted failures."""
        self.calls: list[tuple[str, Stage]] = []
        self.failures: dict[Stage, int] = {}

    def __call__(self, partition: str, stage: Stage) -> None:
        """Record the call; fail while scripted failures remain."""
        self.calls.append((partition, stage))
        if self.failures.get(stage, 0) > 0:
            self.failures[stage] -= 1
            raise RuntimeError("boom")


def _event(
    version: int,
    kind: ChangeType = ChangeType.PRICE_UPDATED,
    store: str = "DE-MUC-017",
    sku: str = "SKU-421",
    event_id: UUID | None = None,
) -> ForecastChangeEvent:
    return ForecastChangeEvent(
        event_id=event_id or uuid4(),
        event_type=kind,
        store_id=store,
        sku=sku,
        occurred_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        entity_version=version,
    )


@pytest.fixture
def setup() -> tuple[
    EventProcessor, Recorder, InMemoryStateStore, InMemoryDeadLetterQueue, list[float]
]:
    store, rec, dlq = InMemoryStateStore(), Recorder(), InMemoryDeadLetterQueue()
    sleeps: list[float] = []
    proc = EventProcessor(store, rec, dlq, RetryPolicy(3, 1.0), sleeps.append)
    return proc, rec, store, dlq, sleeps


def test_price_change_recomputes_all_stages_for_one_partition(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    result = proc.handle(_event(1))
    assert result.outcome is Outcome.PROCESSED
    assert rec.calls == [
        ("DE-MUC-017:SKU-421", Stage.FEATURES),
        ("DE-MUC-017:SKU-421", Stage.FORECAST),
        ("DE-MUC-017:SKU-421", Stage.PROPOSAL),
    ]


def test_stock_change_only_recomputes_the_proposal(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    proc.handle(_event(1, ChangeType.STOCK_UPDATED))
    assert [s for _, s in rec.calls] == [Stage.PROPOSAL]


def test_unrelated_partitions_are_untouched(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    proc.handle(_event(1))
    assert {p for p, _ in rec.calls} == {"DE-MUC-017:SKU-421"}


def test_duplicate_delivery_recomputes_once(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    event = _event(1)
    first, second = proc.handle(event), proc.handle(event)
    assert (first.outcome, second.outcome) == (Outcome.PROCESSED, Outcome.DUPLICATE)
    assert len(rec.calls) == 3


def test_stale_event_is_dropped(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, store, *_ = setup
    proc.handle(_event(5))
    calls_before = len(rec.calls)
    stale = proc.handle(_event(3))
    assert stale.outcome is Outcome.STALE
    assert len(rec.calls) == calls_before
    assert store.latest_version("DE-MUC-017:SKU-421") == 5


def test_out_of_order_batch_runs_once_at_highest_version(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, store, *_ = setup
    results = proc.process_batch([_event(3), _event(1), _event(2)])
    assert [r.outcome for r in results] == [Outcome.PROCESSED] * 3
    assert len(rec.calls) == 3  # one run, not three
    assert store.latest_version("DE-MUC-017:SKU-421") == 3


def test_batch_coalesces_to_the_union_of_stages(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    proc.process_batch(
        [_event(1, ChangeType.STOCK_UPDATED), _event(2, ChangeType.SALES_UPDATED)]
    )
    assert [s for _, s in rec.calls] == [Stage.FEATURES, Stage.FORECAST, Stage.PROPOSAL]


def test_batch_with_duplicate_ids_and_two_partitions(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, *_ = setup
    shared = _event(1)
    other = _event(1, sku="SKU-999")
    results = proc.process_batch([shared, shared, other])
    assert [r.outcome for r in results] == [
        Outcome.PROCESSED,
        Outcome.DUPLICATE,
        Outcome.PROCESSED,
    ]
    assert {p for p, _ in rec.calls} == {"DE-MUC-017:SKU-421", "DE-MUC-017:SKU-999"}


def test_transient_failure_is_retried_with_backoff(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, _, dlq, sleeps = setup
    rec.failures[Stage.FORECAST] = 2
    result = proc.handle(_event(1))
    assert result.outcome is Outcome.PROCESSED
    assert sleeps == [1.0, 2.0]
    assert not dlq.items


def test_exhausted_retries_dead_letter_and_stay_replayable(setup) -> None:  # type: ignore[no-untyped-def]
    proc, rec, store, dlq, _ = setup
    rec.failures[Stage.FORECAST] = 99
    event = _event(1)
    assert proc.handle(event).outcome is Outcome.DEAD_LETTERED
    assert dlq.items[0].attempts == 3
    assert "RuntimeError" in dlq.items[0].error
    assert store.latest_version("DE-MUC-017:SKU-421") == 0  # nothing committed
    assert not store.seen(event.event_id)

    rec.failures.clear()  # the outage is fixed; replay
    replayed = [proc.handle(e) for e in dlq.drain()]
    assert replayed[0].outcome is Outcome.PROCESSED
    assert store.latest_version("DE-MUC-017:SKU-421") == 1


def test_concurrent_commits_keep_the_highest_version() -> None:
    store = InMemoryStateStore()
    threads = [
        threading.Thread(target=store.commit, args=([uuid4()], "p", v))
        for v in range(1, 50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.latest_version("p") == 49


def test_retry_policy_validation() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(0)
    with pytest.raises(ValueError, match="base_delay"):
        RetryPolicy(1, -1)
