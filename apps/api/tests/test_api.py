"""API behaviour: RBAC, outbox atomicity, expiry-aware proposals, four-eyes."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from freshcast_api.config import Settings
from freshcast_api.main import create_app
from freshcast_api.models import AuditLog, OutboxEvent
from tests.conftest import headers

MGR = headers("anna", "store_manager")
MGR2 = headers("ben", "store_manager")
VIEWER = headers("vera", "viewer")

LOT = {
    "store_id": "DE-MUC-001",
    "sku": "STRAWBERRY-500G",
    "lot_id": "LOT-B",
    "quantity": 40,
    "use_by_date": "2026-11-05",
}
PROPOSAL = {
    "store_id": "DE-MUC-001",
    "sku": "STRAWBERRY-500G",
    "as_of_date": "2026-11-01",
    "forecast_units": 120,
    "safety_stock_units": 20,
    "incoming_units": 10,
    "supplier_lead_days": 2,
    "order_multiple": 12,
}


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_or_unknown_credentials_rejected(client: TestClient) -> None:
    assert client.post("/v1/stock-lots", json=LOT).status_code == 401
    bad = headers("x", "root")
    assert client.post("/v1/stock-lots", json=LOT, headers=bad).status_code == 401


def test_viewer_cannot_write(client: TestClient) -> None:
    assert client.post("/v1/stock-lots", json=LOT, headers=VIEWER).status_code == 403


def test_lot_creates_versioned_outbox_event_and_audit(client: TestClient) -> None:
    first = client.post("/v1/stock-lots", json=LOT, headers=MGR)
    second = client.post("/v1/stock-lots", json={**LOT, "lot_id": "LOT-C"}, headers=MGR)
    assert first.status_code == 201
    assert (first.json()["entity_version"], second.json()["entity_version"]) == (1, 2)
    with Session(client.app.state.session_factory.kw["bind"]) as s:  # type: ignore[attr-defined]
        events = s.scalars(select(OutboxEvent)).all()
        assert [e.event_type for e in events] == ["stock.updated"] * 2
        assert {e.partition_key for e in events} == {"DE-MUC-001:STRAWBERRY-500G"}
        assert s.scalars(select(AuditLog)).first().action == "stock_lot.create"  # type: ignore[union-attr]


def test_duplicate_lot_conflict_rolls_back_event(client: TestClient) -> None:
    client.post("/v1/stock-lots", json=LOT, headers=MGR)
    dup = client.post("/v1/stock-lots", json=LOT, headers=MGR)
    assert dup.status_code == 409
    with Session(client.app.state.session_factory.kw["bind"]) as s:  # type: ignore[attr-defined]
        assert len(s.scalars(select(OutboxEvent)).all()) == 1


def test_validation_rejects_negative_quantity_and_unknown_fields(
    client: TestClient,
) -> None:
    bad = client.post("/v1/stock-lots", json={**LOT, "quantity": -1}, headers=MGR)
    extra = client.post("/v1/stock-lots", json={**LOT, "x": 1}, headers=MGR)
    assert bad.status_code == extra.status_code == 422


def test_proposal_uses_stored_lots_and_requires_approval(client: TestClient) -> None:
    client.post("/v1/stock-lots", json=LOT, headers=MGR)
    expiring = {**LOT, "lot_id": "LOT-A", "quantity": 30, "use_by_date": "2026-11-02"}
    client.post("/v1/stock-lots", json=expiring, headers=MGR)
    res = client.post("/v1/proposals", json=PROPOSAL, headers=MGR)
    body = res.json()
    assert res.status_code == 201
    assert (body["usable_stock_units"], body["expiring_stock_units"]) == (40, 30)
    assert body["recommended_order_units"] == 96
    assert body["status"] == "pending"


def test_four_eyes_approval_flow(client: TestClient) -> None:
    pid = client.post("/v1/proposals", json=PROPOSAL, headers=MGR).json()["id"]
    assert client.post(f"/v1/proposals/{pid}/approve", headers=MGR).status_code == 403
    assert (
        client.post(f"/v1/proposals/{pid}/approve", headers=VIEWER).status_code == 403
    )
    ok = client.post(f"/v1/proposals/{pid}/approve", headers=MGR2)
    assert ok.status_code == 200
    assert (ok.json()["status"], ok.json()["approved_by"]) == ("approved", "ben")
    again = client.post(f"/v1/proposals/{pid}/approve", headers=MGR2)
    assert again.status_code == 409
    assert client.get(f"/v1/proposals/{pid}", headers=VIEWER).status_code == 200


def test_unknown_proposal_404(client: TestClient) -> None:
    url = "/v1/proposals/00000000-0000-0000-0000-000000000000"
    assert client.get(url, headers=VIEWER).status_code == 404


def test_non_local_env_refuses_header_auth() -> None:
    from sqlalchemy import create_engine

    app = create_app(
        Settings(env="prod", database_url="sqlite+pysqlite://"),
        create_engine("sqlite+pysqlite://"),
    )
    with TestClient(app) as c:
        assert (
            c.get(
                "/v1/proposals/00000000-0000-0000-0000-000000000000", headers=MGR
            ).status_code
            == 501
        )
