"""The TypeScript mirror must not drift from the authoritative Python states.

``packages/domain/src/workflow.ts`` is used by the web app and the image worker.
If someone adds a state, gate, mode or origin on one side only, this test fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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

TS_WORKFLOW = Path(__file__).resolve().parents[2] / "packages" / "domain" / "src" / "workflow.ts"


def _string_array(source: str, const_name: str) -> list[str]:
    """Read a ``export const NAME = [...] as const`` array of string literals."""
    match = re.search(rf"export const {const_name} = \[(.*?)\] as const", source, re.S)
    if match is None:
        raise AssertionError(f"{const_name} not found in workflow.ts")
    return re.findall(r'"([^"]+)"', match.group(1))


@pytest.fixture(scope="module")
def ts_source() -> str:
    if not TS_WORKFLOW.exists():  # pragma: no cover - repository layout guard
        pytest.skip(f"TypeScript mirror not found at {TS_WORKFLOW}")
    return TS_WORKFLOW.read_text(encoding="utf-8")


def test_run_statuses_match(ts_source: str) -> None:
    assert _string_array(ts_source, "RUN_STATUSES") == [s.value for s in RunStatus]


def test_happy_path_matches(ts_source: str) -> None:
    assert _string_array(ts_source, "HAPPY_PATH") == [s.value for s in HAPPY_PATH]


def test_failure_statuses_match(ts_source: str) -> None:
    assert _string_array(ts_source, "FAILURE_STATUSES") == [s.value for s in FailureStatus]


def test_gates_match(ts_source: str) -> None:
    assert _string_array(ts_source, "APPROVAL_GATES") == [g.value for g in ApprovalGate]


def test_decisions_match(ts_source: str) -> None:
    assert _string_array(ts_source, "APPROVAL_DECISIONS") == [d.value for d in ApprovalDecision]


def test_idea_modes_match(ts_source: str) -> None:
    assert _string_array(ts_source, "IDEA_MODES") == [m.value for m in IdeaMode]


def test_concept_origins_match(ts_source: str) -> None:
    assert _string_array(ts_source, "CONCEPT_ORIGINS") == [o.value for o in ConceptOrigin]


def test_risk_levels_match(ts_source: str) -> None:
    assert _string_array(ts_source, "RISK_LEVELS") == [r.value for r in RiskLevel]


def test_job_statuses_match(ts_source: str) -> None:
    assert _string_array(ts_source, "JOB_STATUSES") == [j.value for j in JobStatus]


def test_terminal_statuses_match(ts_source: str) -> None:
    assert set(_string_array(ts_source, "TERMINAL_STATUSES")) == {
        s.value for s in TERMINAL_STATUSES
    }


def test_in_flight_statuses_match(ts_source: str) -> None:
    """The web app offers Stop, and refuses Delete, on exactly these states."""
    assert set(_string_array(ts_source, "IN_FLIGHT_STATUSES")) == {
        s.value for s in IN_FLIGHT_STATUSES
    }
