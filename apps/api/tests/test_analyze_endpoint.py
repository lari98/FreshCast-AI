"""Upload endpoint: auth, validation errors, size limit and a real forecast."""

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from freshcast.byod.ingest import MAX_BYTES
from tests.conftest import headers

SAMPLES = Path(__file__).resolve().parents[3] / "data/samples"
MANAGER = headers("anna", "store_manager")


def test_requires_authentication_and_role(client: TestClient) -> None:
    files = {"sales": ("s.csv", b"a,b\n1,2\n")}
    assert client.post("/v1/analyze", files=files).status_code == 401
    viewer = client.post("/v1/analyze", files=files, headers=headers("v", "viewer"))
    assert viewer.status_code == 403


def test_problems_are_returned_as_a_list(client: TestClient) -> None:
    files = {"sales": ("s.csv", b"store_id,sku\nA,B\n")}
    r = client.post("/v1/analyze", files=files, headers=MANAGER)
    assert r.status_code == 422
    assert "business_date" in r.json()["detail"]["problems"][0]


def test_oversized_file_is_rejected(client: TestClient) -> None:
    big = b"x" * (MAX_BYTES + 10)
    r = client.post("/v1/analyze", files={"sales": ("s.csv", big)}, headers=MANAGER)
    assert r.status_code == 413


def test_german_sample_files_produce_a_forecast(client: TestClient) -> None:
    files = {
        "sales": ("absatz.csv", (SAMPLES / "beispiel_absatz.csv").read_bytes()),
        "stock": ("bestand.csv", (SAMPLES / "beispiel_bestand.csv").read_bytes()),
    }
    r = client.post("/v1/analyze", files=files, headers=MANAGER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "upload" and len(body["items"]) == 8
    assert body["quality"]["calibrated"] is True
    item = body["items"][0]
    assert item["proposal"]["recommended_order_units"] >= 0
    assert date.fromisoformat(body["as_of"]) > date(2025, 12, 1) + timedelta(days=0)


def test_cors_allows_the_local_dashboard(client: TestClient) -> None:
    r = client.options(
        "/v1/analyze",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
            "access-control-request-headers": "x-dev-user,x-dev-role",
        },
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
