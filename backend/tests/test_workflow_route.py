from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import ConceptOrigin, IdeaMode
from app.domain.workflow import (
    HAPPY_PATH,
    IN_FLIGHT_STATUSES,
    TERMINAL_STATUSES,
    ApprovalDecision,
    ApprovalGate,
    FailureStatus,
    JobStatus,
    RiskLevel,
    RunStatus,
)
from app.main import create_app
from app.settings import Settings

TS_WORKFLOW = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src" / "workflow.ts"


def test_workflow_endpoint_describes_the_pipeline(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/v1/workflow")

    assert response.status_code == 200
    body = response.json()
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


# --- TypeScript domain mirror synchronization -------------------------------


def _string_array(source: str, const_name: str) -> list[str]:
    match = re.search(rf"export const {const_name} = \[(.*?)\] as const", source, re.S)
    if match is None:
        raise AssertionError(f"{const_name} not found in workflow.ts")
    return re.findall(r'"([^"]+)"', match.group(1))


@pytest.fixture(scope="module")
def ts_source() -> str:
    if not TS_WORKFLOW.exists():
        pytest.skip(f"TypeScript mirror not found at {TS_WORKFLOW}")
    return TS_WORKFLOW.read_text(encoding="utf-8")


def test_typescript_workflow_mirror_matches(ts_source: str) -> None:
    assert _string_array(ts_source, "RUN_STATUSES") == [s.value for s in RunStatus]
    assert _string_array(ts_source, "HAPPY_PATH") == [s.value for s in HAPPY_PATH]
    assert _string_array(ts_source, "FAILURE_STATUSES") == [s.value for s in FailureStatus]
    assert _string_array(ts_source, "APPROVAL_GATES") == [g.value for g in ApprovalGate]
    assert _string_array(ts_source, "APPROVAL_DECISIONS") == [d.value for d in ApprovalDecision]
    assert _string_array(ts_source, "IDEA_MODES") == [m.value for m in IdeaMode]
    assert _string_array(ts_source, "CONCEPT_ORIGINS") == [o.value for o in ConceptOrigin]
    assert _string_array(ts_source, "RISK_LEVELS") == [r.value for r in RiskLevel]
    assert _string_array(ts_source, "JOB_STATUSES") == [j.value for j in JobStatus]
    assert set(_string_array(ts_source, "TERMINAL_STATUSES")) == {
        s.value for s in TERMINAL_STATUSES
    }
    assert set(_string_array(ts_source, "IN_FLIGHT_STATUSES")) == {
        s.value for s in IN_FLIGHT_STATUSES
    }
