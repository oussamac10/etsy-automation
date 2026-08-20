from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_workflow_endpoint_describes_the_pipeline(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/v1/workflow")

    assert response.status_code == 200
    body = response.json()
    # Phase 2 extended the pipeline: it now starts at DRAFT, and PUBLISHED /
    # CANCELLED sit after the happy path rather than on it.
    assert body["states"][0] == "DRAFT"
    assert "RESEARCHING" in body["states"]
    assert body["states"][-1] == "CANCELLED"
    assert "ETSY_DRAFT_CREATED" in body["states"]
    assert len(body["gates"]) == 3
    assert body["publishes_automatically"] is False
    assert "safe" not in body["risk_levels"]


def test_every_gate_names_its_source_and_target(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    gates = client.get("/api/v1/workflow").json()["gates"]
    assert {gate["gate"] for gate in gates} == {
        "IDEA_APPROVAL",
        "ARTWORK_APPROVAL",
        "LISTING_APPROVAL",
    }
    for gate in gates:
        assert gate["decided_from"] and gate["advances_to"]


def test_openapi_document_is_generated(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    document = client.get("/api/openapi.json").json()
    assert "/api/health" in document["paths"]
    assert "/api/v1/workflow" in document["paths"]
    assert "/api/v1/workflows/{workflow_id}/gates/listing" in document["paths"]
    assert "/api/v1/workflows/{workflow_id}/gates/gate-3/decision" in document["paths"]
