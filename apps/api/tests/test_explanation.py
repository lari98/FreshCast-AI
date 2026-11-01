"""Explanation endpoint: provenance, fallback and audit."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from freshcast.assistant.client import FakeModel
from freshcast_api.config import Settings
from freshcast_api.db import Base
from freshcast_api.main import create_app
from freshcast_api.models import AuditLog
from tests.conftest import headers
from tests.test_api import PROPOSAL

MGR = headers("anna", "store_manager")
VIEWER = headers("vera", "viewer")


def _client(model: FakeModel | None) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = create_app(
        Settings(env="local", database_url="sqlite+pysqlite://"), engine, model
    )
    return TestClient(app)


def _proposal_id(client: TestClient) -> str:
    return str(client.post("/v1/proposals", json=PROPOSAL, headers=MGR).json()["id"])


def test_without_a_model_the_template_is_returned_in_both_languages() -> None:
    client = _client(None)
    pid = _proposal_id(client)
    de = client.get(f"/v1/proposals/{pid}/explanation?lang=de", headers=VIEWER).json()
    en = client.get(f"/v1/proposals/{pid}/explanation?lang=en", headers=VIEWER).json()
    assert de["source"] == en["source"] == "template"
    assert de["ai_generated"] is False
    assert "Filiale" in de["text"] and "store" in en["text"]
    assert "approve" in en["disclaimer"]


def test_grounded_model_answer_is_marked_as_ai() -> None:
    client = _client(
        FakeModel(
            "Es werden 120 Stück erwartet. Bitte Freigabe durch die Filialleitung."
        )
    )
    pid = _proposal_id(client)
    body = client.get(f"/v1/proposals/{pid}/explanation?lang=de", headers=VIEWER).json()
    assert body["source"] == "model" and body["ai_generated"] is True
    assert body["violations"] == []


def test_hallucinated_numbers_never_reach_the_client() -> None:
    client = _client(FakeModel("Bestellen Sie 777 Stück. Freigabe nötig."))
    pid = _proposal_id(client)
    body = client.get(f"/v1/proposals/{pid}/explanation?lang=de", headers=VIEWER).json()
    assert body["source"] == "template"
    assert "ungrounded_number:777" in body["violations"]
    assert "777" not in body["text"]


def test_explanation_is_audited_and_validated() -> None:
    client = _client(None)
    pid = _proposal_id(client)
    url = f"/v1/proposals/{pid}/explanation"
    assert client.get(url).status_code == 401
    assert client.get(url + "?lang=fr", headers=VIEWER).status_code == 422
    missing = "/v1/proposals/00000000-0000-0000-0000-000000000000/explanation"
    assert client.get(missing, headers=VIEWER).status_code == 404
    client.get(url, headers=VIEWER)
    with Session(client.app.state.session_factory.kw["bind"]) as s:  # type: ignore[attr-defined]
        actions = [a.action for a in s.scalars(select(AuditLog))]
    assert "proposal.explain.template" in actions
