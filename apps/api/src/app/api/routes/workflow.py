"""Read-only description of the workflow.

The web app renders the pipeline and its gates from this endpoint rather than
duplicating the state list, so the UI can never show a stage the backend does
not implement.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.workflow import (
    GATE_SOURCE_STATUS,
    GATE_TARGET_STATUS,
    RUN_ORDER,
    ApprovalGate,
    FailureStatus,
    RiskLevel,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


class GateDescription(BaseModel):
    gate: ApprovalGate
    decided_from: str
    advances_to: str


class WorkflowDescription(BaseModel):
    states: list[str]
    failure_states: list[str]
    gates: list[GateDescription]
    risk_levels: list[str]
    #: Stated in the payload so no client can assume otherwise.
    publishes_automatically: bool = False


@router.get(
    "",
    response_model=WorkflowDescription,
    summary="The authoritative workflow, its failure states and its human gates",
)
async def describe_workflow() -> WorkflowDescription:
    return WorkflowDescription(
        states=[status.value for status in RUN_ORDER],
        failure_states=[status.value for status in FailureStatus],
        gates=[
            GateDescription(
                gate=gate,
                decided_from=GATE_SOURCE_STATUS[gate].value,
                advances_to=GATE_TARGET_STATUS[gate].value,
            )
            for gate in ApprovalGate
        ],
        risk_levels=[level.value for level in RiskLevel],
        publishes_automatically=False,
    )
