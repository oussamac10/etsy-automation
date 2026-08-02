"""Workflow endpoints.

The minimum needed to prove the Phase 2 domain works end to end. Routes parse,
call one use case and map the result; every rule lives below this layer.

Every route requires a session and is scoped to the authenticated owner
(Phase 3, ADR-0002). The owner ID is never read from a request body or query
string; it comes from the session, so a caller cannot act as someone else by
asking to. A workflow belonging to another owner answers ``404``, not ``403``:
see ``docs/authentication-and-secrets.md``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, UowDep
from app.api.schemas import (
    ApprovalResponse,
    CreateWorkflowRequest,
    GateDecisionRequest,
    OriginalIdeaResponse,
    SubmitIdeaRequest,
    TimelineEntryResponse,
    TimelineResponse,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.application import workflows as use_cases
from app.domain.workflow import RunStatus

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product workflow",
)
async def create_workflow(
    payload: CreateWorkflowRequest, user: CurrentUser, uow: UowDep, response: Response
) -> WorkflowResponse:
    workflow = await use_cases.create_workflow(
        uow,
        use_cases.CreateWorkflowCommand(
            # From the session. `CreateWorkflowRequest` has no owner field, so a
            # client cannot even ask to create a workflow for someone else.
            owner_id=user.id,
            idea_mode=payload.idea_mode,
            name=payload.name,
            target_country=payload.target_country,
            output_language=payload.output_language,
            target_marketplace=payload.target_marketplace,
            target_buyer=payload.target_buyer,
            intended_product_uses=payload.intended_product_uses,
        ),
    )
    result = WorkflowResponse.model_validate(workflow)
    response.headers["Location"] = f"/api/v1/workflows/{result.id}"
    return result


@router.get("", response_model=WorkflowListResponse, summary="List product workflows")
async def list_workflows(
    user: CurrentUser,
    uow: UowDep,
    state: RunStatus | None = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowListResponse:
    """Always the caller's own workflows. There is no ``owner_id`` filter."""
    items, total = await use_cases.list_workflows(
        uow,
        owner_id=user.id,
        state=state,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return WorkflowListResponse(
        items=[WorkflowResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Fetch one workflow",
    responses={404: {"description": "No workflow with that ID"}},
)
async def get_workflow(workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep) -> WorkflowResponse:
    workflow = await use_cases.get_workflow(uow, workflow_id, owner_id=user.id)
    return WorkflowResponse.model_validate(workflow)


@router.post(
    "/{workflow_id}/ideas",
    response_model=OriginalIdeaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the owner's original idea, stored verbatim",
    responses={
        404: {"description": "No workflow with that ID"},
        409: {"description": "This workflow already has an original idea"},
        422: {"description": "The idea does not match the workflow's idea mode"},
    },
)
async def submit_idea(
    workflow_id: uuid.UUID, payload: SubmitIdeaRequest, user: CurrentUser, uow: UowDep
) -> OriginalIdeaResponse:
    idea = await use_cases.submit_original_idea(
        uow,
        use_cases.SubmitIdeaCommand(
            workflow_id=workflow_id,
            owner_id=user.id,
            original_text=payload.original_text,
            slogan=payload.slogan,
            desired_style=payload.desired_style,
            audience=payload.audience,
            occasion=payload.occasion,
            season=payload.season,
            product_uses=payload.product_uses,
        ),
    )
    return OriginalIdeaResponse.model_validate(idea)


@router.get(
    "/{workflow_id}/ideas",
    response_model=OriginalIdeaResponse,
    summary="Fetch the preserved original idea",
    responses={404: {"description": "No workflow, or no idea submitted"}},
)
async def get_idea(workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep) -> OriginalIdeaResponse:
    idea = await use_cases.get_original_idea(uow, workflow_id, owner_id=user.id)
    return OriginalIdeaResponse.model_validate(idea)


@router.get(
    "/{workflow_id}/timeline",
    response_model=TimelineResponse,
    summary="Transitions, approvals and audit events in one ordered list",
    responses={404: {"description": "No workflow with that ID"}},
)
async def get_timeline(workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep) -> TimelineResponse:
    workflow = await use_cases.get_workflow(uow, workflow_id, owner_id=user.id)
    entries = await use_cases.get_timeline(uow, workflow_id, owner_id=user.id)
    return TimelineResponse(
        workflow_id=workflow.id,
        state=workflow.state,
        entries=[
            TimelineEntryResponse(
                kind=entry.kind,
                occurred_at=entry.occurred_at,
                summary=entry.summary,
                detail=entry.detail,
            )
            for entry in entries
        ],
    )


@router.post(
    "/{workflow_id}/approvals",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a human decision at one of the three gates",
    responses={
        404: {"description": "No workflow with that ID"},
        409: {"description": "The workflow is not at this gate"},
    },
)
async def decide_gate(
    workflow_id: uuid.UUID, payload: GateDecisionRequest, user: CurrentUser, uow: UowDep
) -> ApprovalResponse:
    approval = await use_cases.decide_gate(
        uow,
        workflow_id,
        owner_id=user.id,
        gate=payload.gate,
        decision=payload.decision,
        actor=user.email,
        target_type=payload.target_type,
        target_id=payload.target_id,
        target_version=payload.target_version,
        comment=payload.comment,
        revision_request=payload.revision_request,
    )
    return ApprovalResponse.model_validate(approval)
