"""SQL state store and Lambda worker behaviour."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from freshcast.events.processor import Stage
from freshcast_api.state_store import SqlStateStore
from freshcast_api.worker import process_sqs_batch


def _factory(client) -> sessionmaker[Session]:  # type: ignore[no-untyped-def]
    return client.app.state.session_factory  # type: ignore[no-any-return]


def _record(version: int, kind: str = "stock.updated", sku: str = "MILK-1L") -> dict:  # type: ignore[type-arg]
    body = {
        "event_id": str(uuid4()),
        "event_type": kind,
        "store_id": "DE-MUC-001",
        "sku": sku,
        "occurred_at": datetime(2026, 11, 1, tzinfo=UTC).isoformat(),
        "entity_version": version,
    }
    return {"messageId": f"m{version}{sku}", "body": json.dumps(body)}


def test_sql_state_store_is_idempotent_and_monotonic(client) -> None:  # type: ignore[no-untyped-def]
    store = SqlStateStore(_factory(client))
    a, b = uuid4(), uuid4()
    assert not store.seen(a)
    store.commit([a], "p", 5)
    store.commit([a, b], "p", 3)  # replay with an older version
    assert store.seen(a) and store.seen(b)
    assert store.latest_version("p") == 5
    assert store.latest_version("other") == 0


def test_worker_processes_and_reports_no_failures(client) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, Stage]] = []
    out = process_sqs_batch(
        [_record(1), _record(2)],
        _factory(client),
        lambda p, s: calls.append((p, s)),
    )
    assert out == {"batchItemFailures": []}
    assert calls == [("DE-MUC-001:MILK-1L", Stage.PROPOSAL)]  # coalesced to one run


def test_worker_reports_failed_and_malformed_messages(client) -> None:  # type: ignore[no-untyped-def]
    def boom(partition: str, stage: Stage) -> None:
        raise RuntimeError("db down")

    good = _record(1)
    bad = {"messageId": "bad", "body": "not json"}
    out = process_sqs_batch([good, bad], _factory(client), boom)
    ids = {f["itemIdentifier"] for f in out["batchItemFailures"]}
    assert ids == {good["messageId"], "bad"}
    # Nothing was committed, so a redelivery can still succeed.
    store = SqlStateStore(_factory(client))
    assert store.latest_version("DE-MUC-001:MILK-1L") == 0


def test_database_url_from_rds_secret_escapes_credentials() -> None:
    from freshcast_api.worker import database_url_from_secret

    secret = {
        "username": "freshcast_admin",
        "password": "p@ss/w:rd",
        "host": "db.internal",
        "port": 5432,
        "dbname": "freshcast",
    }
    url = database_url_from_secret(json.dumps(secret))
    assert url == (
        "postgresql+psycopg://freshcast_admin:p%40ss%2Fw%3Ard@db.internal:5432/freshcast"
    )
