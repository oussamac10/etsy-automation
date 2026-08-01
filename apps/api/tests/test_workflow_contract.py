"""The TypeScript mirror must not drift from the authoritative Python states.

``packages/domain/src/workflow.ts`` is used by the web app and the image worker.
If someone adds a state on one side only, this test fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domain.workflow import ApprovalGate, FailureStatus, RiskLevel, RunStatus

TS_WORKFLOW = Path(__file__).resolve().parents[3] / "packages" / "domain" / "src" / "workflow.ts"


def _string_array(source: str, const_name: str) -> list[str]:
    match = re.search(rf"export const {const_name} = \[(.*?)\] as const;", source, re.S)
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


def test_failure_statuses_match(ts_source: str) -> None:
    assert _string_array(ts_source, "FAILURE_STATUSES") == [s.value for s in FailureStatus]


def test_gates_match(ts_source: str) -> None:
    assert _string_array(ts_source, "APPROVAL_GATES") == [g.value for g in ApprovalGate]


def test_risk_levels_match(ts_source: str) -> None:
    assert _string_array(ts_source, "RISK_LEVELS") == [r.value for r in RiskLevel]
