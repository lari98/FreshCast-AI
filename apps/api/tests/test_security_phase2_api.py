"""Attack phase 2: the HTTP API (upload endpoint, headers, auth, flooding)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from freshcast_api.config import Settings
from freshcast_api.db import Base
from freshcast_api.hardening import RateLimiter
from freshcast_api.main import create_app
from tests.conftest import headers

MANAGER = headers("anna", "store_manager")
HEAD = b"store_id,sku,business_date,units_sold\n"


def _client(**settings: object) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    cfg = Settings(database_url="sqlite+pysqlite://", **settings)  # type: ignore[arg-type]
    return TestClient(create_app(cfg, engine))


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("sales.csv", b"MZ\x90\x00" + b"\x00" * 100),
        ("sales.csv", b"PK\x03\x04" + b"\x00" * 100),
        ("sales.csv", HEAD + b"A,<script>alert(1)</script>,2026-01-02,5\n"),
        ("sales.exe", HEAD),
        ("../../etc/passwd.csv", HEAD),
        ("sales.csv.bat", HEAD),
    ],
)
def test_hostile_uploads_get_422_with_a_reason(
    client: TestClient, name: str, body: bytes
) -> None:
    r = client.post("/v1/analyze", files={"sales": (name, body)}, headers=MANAGER)
    assert r.status_code == 422
    assert r.json()["detail"]["problems"]
    assert "Traceback" not in r.text


def test_stock_file_is_checked_like_the_sales_file(client: TestClient) -> None:
    files = {"sales": ("s.csv", HEAD), "stock": ("b.csv", b"MZ" + b"\x00" * 20)}
    r = client.post("/v1/analyze", files=files, headers=MANAGER)
    assert r.status_code == 422


def test_unreachable_scanner_blocks_uploads() -> None:
    client = _client(env="local", clamd_host="127.0.0.1", clamd_port=1)
    r = client.post("/v1/analyze", files={"sales": ("s.csv", HEAD)}, headers=MANAGER)
    assert r.status_code == 422
    assert "not reachable" in r.text


def test_security_headers_are_set_on_every_response(client: TestClient) -> None:
    for path in ("/health", "/v1/analyze"):
        r = client.get(path)
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in r.headers["content-security-policy"]


def test_dev_headers_are_useless_outside_local() -> None:
    client = _client(env="prod")
    r = client.post("/v1/analyze", files={"sales": ("s.csv", HEAD)}, headers=MANAGER)
    assert r.status_code == 501  # nobody gets in with a made-up header


@pytest.mark.parametrize("role", ["root", "ADMIN ", "admin;viewer", "", "../admin"])
def test_role_spoofing_is_rejected(client: TestClient, role: str) -> None:
    r = client.post(
        "/v1/analyze",
        files={"sales": ("s.csv", HEAD)},
        headers={"x-dev-user": "mallory", "x-dev-role": role},
    )
    assert r.status_code == 401


def test_viewer_cannot_upload(client: TestClient) -> None:
    r = client.post(
        "/v1/analyze",
        files={"sales": ("s.csv", HEAD)},
        headers=headers("v", "viewer"),
    )
    assert r.status_code == 403


def test_oversized_request_is_refused_before_it_is_read(client: TestClient) -> None:
    r = client.post(
        "/v1/analyze",
        content=b"x",
        headers={**MANAGER, "content-length": str(10**10)},
    )
    assert r.status_code == 413
    assert (
        client.post(
            "/v1/analyze", content=b"x", headers={"content-length": "-5"}
        ).status_code
        == 413
    )


def test_flooding_the_upload_endpoint_is_throttled() -> None:
    client = _client(env="local", analyze_rate_limit_per_minute=3)
    codes = [
        client.post(
            "/v1/analyze", files={"sales": ("s.csv", HEAD)}, headers=MANAGER
        ).status_code
        for _ in range(6)
    ]
    assert codes[:3] == [422, 422, 422]
    assert set(codes[3:]) == {429}
    assert (
        client.post(
            "/v1/analyze", files={"sales": ("s.csv", HEAD)}, headers=MANAGER
        ).headers["retry-after"]
        == "60"
    )


def test_rate_limit_window_slides() -> None:
    limiter = RateLimiter()
    assert all(limiter.allow("ip", "b", 2, now=t) for t in (0.0, 1.0))
    assert not limiter.allow("ip", "b", 2, now=2.0)
    assert limiter.allow("ip", "b", 2, now=61.5)
    assert limiter.allow("other", "b", 2, now=2.0)


def test_cors_does_not_allow_foreign_origins(client: TestClient) -> None:
    r = client.options(
        "/v1/analyze",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers


def test_sql_injection_in_ids_is_inert(client: TestClient) -> None:
    r = client.get("/v1/stores/' OR 1=1 --/inventory", headers=MANAGER)
    assert r.status_code in (404, 422)
    assert "OR 1=1" not in r.text or r.status_code == 404
