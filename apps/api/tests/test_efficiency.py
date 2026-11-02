"""Efficiency and resilience: result cache, load gate, compression, readiness."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from freshcast_api.efficiency import Busy, LoadGate, ResultCache, cache_key
from tests.conftest import headers

SAMPLES = Path(__file__).resolve().parents[3] / "data/samples"
MANAGER = headers("anna", "store_manager")


def _files() -> dict[str, tuple[str, bytes]]:
    return {
        "sales": ("a.csv", (SAMPLES / "beispiel_absatz.csv").read_bytes()),
        "stock": ("b.csv", (SAMPLES / "beispiel_bestand.csv").read_bytes()),
    }


def test_cache_key_depends_on_every_input() -> None:
    base = cache_key(b"a", b"b", "2026-01-01")
    assert base == cache_key(b"a", b"b", "2026-01-01")
    assert base != cache_key(b"a", b"c", "2026-01-01")
    assert base != cache_key(b"a", None, "2026-01-01")
    assert base != cache_key(b"a", b"b", "2026-01-02")
    # shifting a byte between the two files must not collide
    assert cache_key(b"ab", b"c", 1) != cache_key(b"a", b"bc", 1)


def test_result_cache_is_lru_and_expires() -> None:
    cache = ResultCache(entries=2, ttl_seconds=10)
    cache.put("a", {"v": 1}, now=0)
    cache.put("b", {"v": 2}, now=0)
    assert cache.get("a", now=1) == {"v": 1}  # a is now the most recently used
    cache.put("c", {"v": 3}, now=2)  # evicts b
    assert cache.get("b", now=2) is None
    assert cache.get("c", now=2) == {"v": 3}
    assert cache.get("a", now=11) is None  # older than the time limit
    off = ResultCache(entries=0, ttl_seconds=10)
    off.put("x", {"v": 1})
    assert off.get("x") is None


def test_load_gate_refuses_instead_of_queueing() -> None:
    gate = LoadGate(1)
    with gate.slot(), pytest.raises(Busy), gate.slot():
        pass
    with gate.slot():  # released again after the block
        pass


def test_identical_upload_is_served_from_cache(client: TestClient) -> None:
    with patch(
        "freshcast_api.routers.analyze.analyze",
        wraps=__import__("freshcast.byod.analyze", fromlist=["analyze"]).analyze,
    ) as spy:
        first = client.post("/v1/analyze", files=_files(), headers=MANAGER)
        second = client.post("/v1/analyze", files=_files(), headers=MANAGER)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert spy.call_count == 1


def test_busy_server_answers_503_with_retry_after(client: TestClient) -> None:
    app = client.app
    gate: LoadGate = app.state.analyze_gate  # type: ignore[attr-defined]
    limit = app.state.settings.analyze_max_concurrent  # type: ignore[attr-defined]
    with ExitStack() as stack:
        for _ in range(limit):
            stack.enter_context(gate.slot())
        r = client.post("/v1/analyze", files=_files(), headers=MANAGER)
    assert r.status_code == 503
    assert r.headers["retry-after"] == "5"


def test_large_answers_are_compressed(client: TestClient) -> None:
    r = client.post(
        "/v1/analyze", files=_files(), headers={**MANAGER, "accept-encoding": "gzip"}
    )
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_readiness_checks_the_database(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
