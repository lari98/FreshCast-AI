"""Outbox publishing and the end-to-end incremental flow."""

import contextlib

from fastapi.testclient import TestClient

from freshcast.events.contracts import ForecastChangeEvent
from freshcast.events.memory import InMemoryDeadLetterQueue, InMemoryStateStore
from freshcast.events.processor import EventProcessor, Outcome, Stage
from freshcast_api.publisher import publish_pending
from tests.conftest import headers

MGR = headers("anna", "store_manager")


def _lot(client: TestClient, lot_id: str, sku: str = "MILK-1L") -> None:
    body = {
        "store_id": "DE-MUC-001",
        "sku": sku,
        "lot_id": lot_id,
        "quantity": 10,
        "use_by_date": "2026-11-09",
    }
    assert client.post("/v1/stock-lots", json=body, headers=MGR).status_code == 201


class ListSink:
    """Sink that collects events; can be told to fail on the Nth send."""

    def __init__(self, fail_on: int | None = None) -> None:
        """Create an empty sink."""
        self.events: list[ForecastChangeEvent] = []
        self.fail_on = fail_on

    def send(self, event: ForecastChangeEvent) -> None:
        """Collect the event or raise on the configured call."""
        if self.fail_on is not None and len(self.events) == self.fail_on:
            raise ConnectionError("bus unavailable")
        self.events.append(event)


def test_publish_marks_events_and_is_not_repeated(client: TestClient) -> None:
    _lot(client, "L1")
    _lot(client, "L2")
    factory = client.app.state.session_factory
    sink = ListSink()
    assert publish_pending(factory, sink) == 2
    assert [e.entity_version for e in sink.events] == [1, 2]
    assert publish_pending(factory, sink) == 0  # nothing left


def test_failure_leaves_remaining_events_unpublished(client: TestClient) -> None:
    for i in range(3):
        _lot(client, f"L{i}")
    factory = client.app.state.session_factory
    failing = ListSink(fail_on=1)
    with contextlib.suppress(ConnectionError):
        publish_pending(factory, failing)
    assert len(failing.events) == 1  # first one went out and was marked
    assert publish_pending(factory, ListSink()) == 2  # retry sends the rest


def test_end_to_end_stock_receipt_recomputes_only_the_proposal(
    client: TestClient,
) -> None:
    calls: list[tuple[str, Stage]] = []
    processor = EventProcessor(
        InMemoryStateStore(),
        lambda partition, stage: calls.append((partition, stage)),
        InMemoryDeadLetterQueue(),
    )
    _lot(client, "L1")
    _lot(client, "L2")  # same partition, second version
    _lot(client, "L3", sku="BREAD-WHEAT-750G")  # different partition
    sink = ListSink()
    publish_pending(client.app.state.session_factory, sink)

    results = processor.process_batch(sink.events)
    assert all(r.outcome is Outcome.PROCESSED for r in results)
    assert sorted(calls) == [
        ("DE-MUC-001:BREAD-WHEAT-750G", Stage.PROPOSAL),
        ("DE-MUC-001:MILK-1L", Stage.PROPOSAL),  # two events, one recompute
    ]

    # At-least-once redelivery of the same events changes nothing.
    again = processor.process_batch(sink.events)
    assert all(r.outcome is Outcome.DUPLICATE for r in again)
    assert len(calls) == 2
