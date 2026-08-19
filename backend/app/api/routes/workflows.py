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

import base64
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from app.api.dependencies import CipherDep, CurrentUser, SettingsDep, StorageDep, UowDep
from app.api.schemas import (
    ApprovalResponse,
    ArtworkJobResponse,
    AssetResponse,
    ConceptRevisionRequest,
    CreateWorkflowRequest,
    DesignPromptResponse,
    Gate3DecisionRequest,
    GateDecisionRequest,
    GenerateArtworkRequest,
    ListingDraftResponse,
    OriginalIdeaResponse,
    ProductConceptResponse,
    ProductionJobResponse,
    RefineArtworkRequest,
    ReorderMockupsRequest,
    ResearchRunResponse,
    RestoreListingVersionRequest,
    StartProductionRequest,
    SubmitIdeaRequest,
    TimelineEntryResponse,
    TimelineResponse,
    UpdateListingDraftRequest,
    UpdateMockupSuggestionsRequest,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.application import workflows as use_cases
from app.application.artwork import ensure_artwork_within_budget
from app.application.production import start_production_job
from app.application.research import queue_research_run
from app.application.unit_of_work import UnitOfWork
from app.domain import ip_risk
from app.domain.enums import ConceptStatus, ProviderName
from app.domain.mockup_compositor import recomposite_workflow_mockups
from app.domain.workflow import JobStatus, RiskLevel, RunStatus
from app.infrastructure.models import ArtworkJob, Asset, ProductionJob
from app.providers.s3 import S3ObjectStorage
from app.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

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
    "/{workflow_id}/cancel",
    response_model=WorkflowResponse,
    summary="Cancel an active workflow",
)
async def cancel_workflow(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
) -> WorkflowResponse:
    """Stop a running campaign. Already stopped or published answers 409."""
    workflow = await use_cases.cancel_workflow(uow, workflow_id, owner_id=user.id, actor=user.email)
    return WorkflowResponse.model_validate(workflow)


@router.post(
    "/{workflow_id}/rerun",
    response_model=WorkflowResponse,
    summary="Resume or rerun a cancelled workflow",
)
async def rerun_workflow(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    from_scratch: bool = False,
) -> WorkflowResponse:
    """Smart-resumes a stopped campaign from its furthest completed step (preserving tokens).

    If from_scratch is True, restarts from DRAFT into a fresh research run.
    """
    workflow = await use_cases.rerun_workflow(
        uow,
        workflow_id,
        owner_id=user.id,
        provider_mode=get_settings().provider_mode,
        actor=user.email,
        from_scratch=from_scratch,
    )
    return WorkflowResponse.model_validate(workflow)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a campaign from the owner's list",
    responses={
        404: {"description": "No workflow with that ID"},
        409: {"description": "A job still owns this workflow; stop it first"},
    },
)
async def delete_workflow(workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep) -> Response:
    """Archive the campaign.

    The rows stay: audit, approval, cost and provenance records are never
    destroyed by an application flow, so this hides the campaign rather than
    deleting it. Repeating the call is a no-op.
    """
    await use_cases.archive_workflow(uow, workflow_id, owner_id=user.id, actor=user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post(
    "/{workflow_id}/research",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a new research run for this workflow",
)
async def enqueue_research(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ResearchRunResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    # A replayed key returns the run it created rather than queueing a second
    # one. Scoped to this workflow so that a client reusing a key across
    # workflows gets a conflict instead of another workflow's run.
    if idempotency_key:
        existing_run = await uow.research.get_run_by_idempotency_key(idempotency_key)
        if existing_run is not None:
            if existing_run.workflow_id != workflow_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key already used for a different workflow",
                )
            return ResearchRunResponse.model_validate(existing_run)

    run = await queue_research_run(
        uow,
        workflow,
        provider_mode=get_settings().provider_mode,
        actor=user.email,
        reason="Manual research trigger",
        idempotency_key=idempotency_key,
    )
    await uow.commit()

    return ResearchRunResponse.model_validate(run)


@router.get(
    "/{workflow_id}/research",
    response_model=list[ResearchRunResponse],
    summary="List research runs for this workflow",
)
async def list_research_runs(
    workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep
) -> list[ResearchRunResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    runs = await uow.research.list_runs_for_workflow(workflow_id)
    return [ResearchRunResponse.model_validate(run) for run in runs]


@router.get(
    "/{workflow_id}/concepts",
    response_model=list[ProductConceptResponse],
    summary="List product concepts for this workflow",
)
async def list_concepts(
    workflow_id: uuid.UUID, user: CurrentUser, uow: UowDep
) -> list[ProductConceptResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    results = []
    for concept in concepts:
        prompts = await uow.concepts.prompts(concept.id)
        concept_dict = {
            "id": concept.id,
            "workflow_id": concept.workflow_id,
            "original_idea_id": concept.original_idea_id,
            "research_run_id": concept.research_run_id,
            "title": concept.title,
            "description": concept.description,
            "origin": concept.origin.value,
            "differentiation": concept.differentiation,
            "target_buyer": concept.target_buyer,
            "buyer_use_case": concept.buyer_use_case,
            "seasonality": concept.seasonality.value,
            "risk_level": concept.risk_level.value,
            "risk_note": concept.risk_note,
            "score": concept.score,
            "score_breakdown": concept.score_breakdown,
            "score_explanation": concept.score_explanation,
            "status": concept.status.value,
            "created_at": concept.created_at,
            "intended_product_uses": concept.intended_product_uses or [],
            "prompts": [DesignPromptResponse.model_validate(p) for p in prompts],
        }
        results.append(ProductConceptResponse.model_validate(concept_dict))
    return results


@router.post(
    "/{workflow_id}/concepts/{concept_id}/revise",
    response_model=DesignPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append a revised version of a concept prompt",
)
async def revise_concept(
    workflow_id: uuid.UUID,
    concept_id: uuid.UUID,
    payload: ConceptRevisionRequest,
    user: CurrentUser,
    uow: UowDep,
) -> DesignPromptResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    concept = await uow.concepts.get(concept_id)
    if not concept or concept.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No concept with that ID in this workflow",
        )

    # A revision can introduce a phrase the research run never saw, so the
    # screen re-runs against the new slogan before the version is appended.
    flagged = ip_risk.scan(concept.title, concept.description, payload.exact_slogan)
    if flagged:
        concept.risk_level = RiskLevel.HIGH
        concept.risk_note = f"Trademark brand names flagged in revision: {', '.join(flagged)}."
    else:
        concept.risk_level = RiskLevel.LOW
        concept.risk_note = "Revision passed the preliminary phrase screen; not a clearance."

    # Append prompt version N+1
    prompt = await uow.concepts.add_prompt_version(
        concept,
        positive_prompt=payload.positive_prompt,
        negative_prompt=payload.negative_prompt,
        typography_instructions=payload.typography_instructions,
        exact_slogan=payload.exact_slogan,
        change_note=payload.change_note,
    )

    # Re-screen concept with USPTO provider if available
    try:
        from app.application.trademark import TrademarkScreeningService
        settings = get_settings()
        primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
            await _resolve_trademark_provider(workflow.owner_id, uow, settings)
        )
        trademark_service = TrademarkScreeningService(
            primary_provider,
            fallback_provider=fallback_provider,
            tsdr_adapter=tsdr_adapter,
            dataset_updated_at=dataset_updated_at,
        )
        tm_risk, tm_findings = await trademark_service.screen_concept_trademark(
            slogan=payload.exact_slogan,
            title=concept.title,
            description=concept.description,
        )
        concept.risk_level = tm_risk
        reasons_list = tm_findings.get("reasons", [])
        if reasons_list:
            concept.risk_note = "; ".join(reasons_list)
        breakdown = dict(concept.score_breakdown or {})
        breakdown["trademark_report"] = tm_findings
        concept.score_breakdown = breakdown
    except Exception as tm_exc:
        logger.warning("revise_concept_trademark_screen_failed", error=str(tm_exc))

    await uow.commit()

    return DesignPromptResponse.model_validate(prompt)


@router.post(
    "/{workflow_id}/concepts/{concept_id}/screen-trademark",
    response_model=ProductConceptResponse,
    summary="Screen concept title and slogan against USPTO trademark registry",
)
async def screen_concept_trademark_endpoint(
    workflow_id: uuid.UUID,
    concept_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    settings: SettingsDep,
) -> ProductConceptResponse:
    from app.application.trademark import TrademarkScreeningService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    concept = await uow.concepts.get(concept_id)
    if not concept or concept.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No concept with that ID in this workflow",
        )

    prompts = await uow.concepts.prompts(concept.id)
    latest_slogan = prompts[-1].exact_slogan if prompts else None

    primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
        await _resolve_trademark_provider(workflow.owner_id, uow, settings)
    )
    trademark_service = TrademarkScreeningService(
        primary_provider,
        fallback_provider=fallback_provider,
        tsdr_adapter=tsdr_adapter,
        dataset_updated_at=dataset_updated_at,
    )

    risk_level, findings = await trademark_service.screen_concept_trademark(
        slogan=latest_slogan,
        title=concept.title,
        description=concept.description,
    )

    concept.risk_level = risk_level
    reasons_list = findings.get("reasons", [])
    if reasons_list:
        concept.risk_note = "; ".join(reasons_list)
    else:
        concept.risk_note = "Passed preliminary USPTO trademark screening."

    breakdown = dict(concept.score_breakdown or {})
    breakdown["trademark_report"] = findings
    concept.score_breakdown = breakdown

    await uow.commit()

    concept_dict = {
        "id": concept.id,
        "workflow_id": concept.workflow_id,
        "original_idea_id": concept.original_idea_id,
        "research_run_id": concept.research_run_id,
        "title": concept.title,
        "description": concept.description,
        "origin": concept.origin.value if hasattr(concept.origin, "value") else str(concept.origin),
        "differentiation": concept.differentiation,
        "target_buyer": concept.target_buyer,
        "buyer_use_case": concept.buyer_use_case,
        "seasonality": concept.seasonality.value if hasattr(concept.seasonality, "value") else str(concept.seasonality),
        "risk_level": concept.risk_level.value if hasattr(concept.risk_level, "value") else str(concept.risk_level),
        "risk_note": concept.risk_note,
        "score": concept.score,
        "score_breakdown": concept.score_breakdown,
        "score_explanation": concept.score_explanation,
        "status": concept.status.value if hasattr(concept.status, "value") else str(concept.status),
        "created_at": concept.created_at,
        "prompts": [DesignPromptResponse.model_validate(p) for p in prompts],
    }
    return ProductConceptResponse.model_validate(concept_dict)


def to_asset_response(asset: Asset, url: str | None = None) -> AssetResponse:
    return AssetResponse(
        id=asset.id,
        workflow_id=asset.workflow_id,
        artwork_job_id=asset.artwork_job_id,
        derived_from_id=asset.derived_from_id,
        storage_key=asset.storage_key,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        checksum_sha256=asset.checksum_sha256,
        width=asset.width,
        height=asset.height,
        has_alpha=asset.has_alpha,
        has_transparent_pixels=asset.has_transparent_pixels,
        provenance=asset.provenance,
        created_at=asset.created_at or datetime.now(UTC),
        url=url,
    )


def to_job_response(
    job: ArtworkJob, assets: list[AssetResponse] | None = None
) -> ArtworkJobResponse:
    return ArtworkJobResponse(
        id=job.id,
        workflow_id=job.workflow_id,
        concept_id=job.concept_id,
        prompt_id=job.prompt_id,
        provider=job.provider.value,
        provider_model=job.provider_model,
        provider_job_id=job.provider_job_id,
        idempotency_key=job.idempotency_key,
        status=job.status.value,
        attempt_count=job.attempt_count,
        requested_width=job.requested_width,
        requested_height=job.requested_height,
        quality=job.quality,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failure_kind=job.failure_kind,
        failure_message=job.failure_message,
        created_at=job.created_at,
        assets=assets or [],
    )


@router.post(
    "/{workflow_id}/artwork",
    response_model=ArtworkJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger artwork generation for this workflow",
)
async def generate_artwork(
    workflow_id: uuid.UUID,
    payload: GenerateArtworkRequest,
    user: CurrentUser,
    uow: UowDep,
    force_new: bool = False,
) -> ArtworkJobResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    if workflow.state not in (
        RunStatus.IDEA_APPROVED,
        "ART_GENERATION_FAILED",
        RunStatus.ART_REVIEW,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow is not in a generateable state: currently in {workflow.state}",
        )

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    approved_concept = next((c for c in concepts if c.status == ConceptStatus.APPROVED), None)
    if not approved_concept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved concept found for this workflow. Approve one first.",
        )

    prompts = await uow.concepts.prompts(approved_concept.id)
    if not prompts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved concept has no design prompts.",
        )
    latest_prompt = prompts[-1]

    settings = get_settings()
    provider_val = payload.provider or "recraft"
    model_val = payload.provider_model
    if not model_val:
        model_val = "recraftv4_1" if provider_val == "recraft" else "gemini-3.1-flash-image"

    provider_enum = ProviderName.RECRAFT if provider_val == "recraft" else ProviderName.GEMINI
    candidate_count = 4 if "pro" not in model_val.lower() else 1

    await ensure_artwork_within_budget(
        uow,
        owner_id=user.id,
        provider=provider_val,
        model=model_val,
        candidate_count=candidate_count,
        provider_mode=settings.provider_mode,
    )

    if not force_new:
        idempotency_key = (
            f"art-{workflow_id}-{latest_prompt.id}-{candidate_count}-{provider_val}-{model_val}"
        )
    else:
        rand_suffix = uuid.uuid4().hex[:8]
        idempotency_key = (
            f"art-{workflow_id}-{latest_prompt.id}-"
            f"{candidate_count}-{provider_val}-{model_val}-{rand_suffix}"
        )

    if not force_new:
        existing_job = await uow.artwork_jobs.get_by_idempotency_key(idempotency_key)
        if existing_job:
            assets = await uow.assets.list_for_job(existing_job.id)
            if len(assets) > 0 and existing_job.status == JobStatus.SUCCEEDED:
                storage = S3ObjectStorage(
                    endpoint_url=settings.s3_endpoint_url,
                    bucket_name=settings.s3_bucket,
                    access_key_id=settings.s3_access_key_id,
                    secret_access_key=settings.s3_secret_access_key.get_secret_value(),
                    region_name=settings.s3_region,
                    force_path_style=settings.s3_force_path_style,
                    public_endpoint_url=settings.s3_public_endpoint_url,
                )
                asset_resps = []
                for asset in assets:
                    url = await storage.signed_url(asset.storage_key, 3600)
                    asset_resps.append(to_asset_response(asset, url))
                return to_job_response(existing_job, asset_resps)
            else:
                existing_job.status = JobStatus.QUEUED
                existing_job.provider = provider_enum
                existing_job.provider_model = model_val
                existing_job.requested_width = payload.requested_width
                existing_job.requested_height = payload.requested_height
                existing_job.quality = payload.quality

                if workflow.state != RunStatus.ART_QUEUED:
                    await uow.workflows.transition(
                        workflow,
                        to_state=RunStatus.ART_QUEUED,
                        expected_version=workflow.version,
                        reason="Triggered artwork generation",
                        actor=user.email,
                    )

                await uow.outbox.add(
                    "run_artwork_task",
                    {"workflow_id": str(workflow_id), "job_id": str(existing_job.id)},
                )
                await uow.commit()
                return to_job_response(existing_job)

    from app.infrastructure.models import ArtworkJob

    job = ArtworkJob(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        concept_id=approved_concept.id,
        prompt_id=latest_prompt.id,
        provider=provider_enum,
        provider_model=model_val,
        idempotency_key=idempotency_key,
        status=JobStatus.QUEUED,
        attempt_count=0,
        requested_width=payload.requested_width,
        requested_height=payload.requested_height,
        quality=payload.quality,
    )
    await uow.artwork_jobs.add(job)

    await uow.workflows.transition(
        workflow,
        to_state=RunStatus.ART_QUEUED,
        expected_version=workflow.version,
        reason="Triggered artwork generation",
        actor=user.email,
    )

    await uow.outbox.add(
        "run_artwork_task",
        {"workflow_id": str(workflow_id), "job_id": str(job.id)},
    )
    await uow.commit()

    return to_job_response(job)


@router.get(
    "/{workflow_id}/artwork-jobs",
    response_model=list[ArtworkJobResponse],
    summary="List artwork generation jobs for this workflow",
)
async def list_artwork_jobs(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
) -> list[ArtworkJobResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    settings = get_settings()
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    jobs = await uow.artwork_jobs.list_for_workflow(workflow_id)
    responses = []
    for job in jobs:
        assets = await uow.assets.list_for_job(job.id)
        asset_resps = []
        for asset in assets:
            url = await storage.signed_url(asset.storage_key, 3600)
            asset_resps.append(to_asset_response(asset, url))
        responses.append(to_job_response(job, asset_resps))

    return responses


@router.post(
    "/{workflow_id}/artwork/regenerate",
    response_model=ArtworkJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Force a new artwork generation run",
)
async def regenerate_artwork(
    workflow_id: uuid.UUID,
    payload: GenerateArtworkRequest,
    user: CurrentUser,
    uow: UowDep,
) -> ArtworkJobResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    if workflow.state not in (
        RunStatus.ART_REVIEW,
        "ART_GENERATION_FAILED",
        RunStatus.ARTWORK_APPROVED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot regenerate artwork unless artwork was already generated or failed.",
        )

    if workflow.state == RunStatus.ART_REVIEW:
        from app.domain.workflow import ApprovalDecision, ApprovalGate

        await use_cases.decide_gate(
            uow=uow,
            workflow_id=workflow_id,
            owner_id=user.id,
            gate=ApprovalGate.ARTWORK_APPROVAL,
            decision=ApprovalDecision.REJECTED,
            actor=user.email,
            target_type="ArtworkJob",
            target_id=None,
            comment="Triggered artwork regeneration",
        )
    elif workflow.state != RunStatus.IDEA_APPROVED:
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.IDEA_APPROVED,
            expected_version=workflow.version,
            reason="Triggered artwork regeneration",
            actor=user.email,
        )
        await uow.commit()

    return await generate_artwork(workflow_id, payload, user, uow, force_new=True)


@router.post(
    "/{workflow_id}/artwork/refine",
    response_model=ArtworkJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a refinement of an existing candidate asset using Gemini",
)
async def refine_artwork(
    workflow_id: uuid.UUID,
    payload: RefineArtworkRequest,
    user: CurrentUser,
    uow: UowDep,
) -> ArtworkJobResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    if workflow.state not in (RunStatus.ART_REVIEW, "ART_GENERATION_FAILED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot refine artwork unless in ART_REVIEW or failure state.",
        )

    candidate_asset = await uow.assets.get(payload.candidate_asset_id)
    if not candidate_asset or candidate_asset.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate asset not found or not in this workflow.",
        )

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    approved_concept = next((c for c in concepts if c.status == ConceptStatus.APPROVED), None)
    if not approved_concept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved concept found. Approve one first.",
        )

    prompts = await uow.concepts.prompts(approved_concept.id)
    if not prompts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved concept has no design prompts.",
        )
    base_prompt = prompts[0]

    settings = get_settings()

    # Automatically enhance the provider prompt with strict reference preservation instructions
    enhancement_prefix = (
        "Use the provided image as the main reference. "
        "Preserve the existing composition, subject placement, visual style, "
        "palette, proportions, typography, and all unaffected elements. "
        "Apply only the requested change. Do not redesign the whole image. "
    )
    combined_positive = (
        f"{enhancement_prefix}Refinement instructions: {payload.positive_prompt}"
        if payload.positive_prompt
        else f"{enhancement_prefix}Refine the artwork design."
    )

    refined_prompt = await uow.concepts.add_prompt_version(
        approved_concept,
        positive_prompt=combined_positive,
        negative_prompt=payload.negative_prompt or base_prompt.negative_prompt,
        typography_instructions=base_prompt.typography_instructions,
        exact_slogan=base_prompt.exact_slogan,
        change_note=payload.change_note,
        generation_metadata={"reference_asset_id": str(payload.candidate_asset_id)},
    )

    # Primary refinement provider: Recraft V3 (with Gemini Image as fallback in worker)
    provider_val = "recraft"
    model_val = settings.recraft_refinement_model
    provider_enum = ProviderName.RECRAFT
    candidate_count = 2

    await ensure_artwork_within_budget(
        uow,
        owner_id=user.id,
        provider=provider_val,
        model=model_val,
        candidate_count=candidate_count,
        provider_mode=settings.provider_mode,
    )

    idempotency_key = f"art-{workflow_id}-{refined_prompt.id}-{candidate_count}"

    from app.infrastructure.models import ArtworkJob

    job = ArtworkJob(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        concept_id=approved_concept.id,
        prompt_id=refined_prompt.id,
        provider=provider_enum,
        provider_model=model_val,
        idempotency_key=idempotency_key,
        status=JobStatus.QUEUED,
        attempt_count=0,
        requested_width=candidate_asset.width or 1024,
        requested_height=candidate_asset.height or 1024,
        quality="standard",
    )
    await uow.artwork_jobs.add(job)

    from app.domain.workflow import ApprovalDecision, ApprovalGate

    await use_cases.decide_gate(
        uow=uow,
        workflow_id=workflow_id,
        owner_id=user.id,
        gate=ApprovalGate.ARTWORK_APPROVAL,
        decision=ApprovalDecision.REVISION_REQUESTED,
        actor=user.email,
        target_type="Asset",
        target_id=payload.candidate_asset_id,
        target_version=refined_prompt.version,
        comment=payload.change_note,
        revision_request=payload.positive_prompt,
    )

    await uow.outbox.add(
        "run_artwork_task",
        {"workflow_id": str(workflow_id), "job_id": str(job.id)},
    )
    await uow.commit()

    return to_job_response(job)


async def to_production_job_response(
    job: ProductionJob,
    storage: S3ObjectStorage,
    uow: UnitOfWork,
) -> ProductionJobResponse:
    master_asset_resp: AssetResponse | None = None
    if job.output_asset_id is not None:
        master_asset = await uow.assets.get(job.output_asset_id)
        if master_asset is not None:
            url = await storage.signed_url(master_asset.storage_key, 3600)
            master_asset_resp = to_asset_response(master_asset, url)

    mockup_resps: list[AssetResponse] = []
    mockup_urls: dict[str, str] = {}

    from app.domain.mockup_products import normalize_product_type
    from app.domain.production_resolver import filter_active_user_mockups

    all_wf_assets = await uow.assets.list_for_workflow(job.workflow_id)
    sorted_mockups = filter_active_user_mockups(all_wf_assets, master_asset_id=job.output_asset_id)

    for asset in sorted_mockups:
        url = await storage.signed_url(asset.storage_key, 86400 * 7)
        if not any(r.id == asset.id for r in mockup_resps):
            mockup_resps.append(to_asset_response(asset, url))

        p_name = None
        if asset.provenance:
            p_name = asset.provenance.get("product_type")
        if not p_name:
            parts = asset.storage_key.split("/")
            fname = parts[-1]
            if "custom_" in fname:
                p_name = fname.split("custom_")[1].split("_")[0]
            else:
                p_name = fname.split(".")[0]

        if p_name:
            canonical_p = normalize_product_type(str(p_name)) or str(p_name).lower()
            if canonical_p not in mockup_urls:
                mockup_urls[canonical_p] = url

    return ProductionJobResponse(
        id=job.id,
        workflow_id=job.workflow_id,
        source_asset_id=job.source_asset_id,
        output_asset_id=job.output_asset_id,
        operations=job.operations,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        idempotency_key=job.idempotency_key,
        attempt_count=job.attempt_count,
        qa_report=job.qa_report or {},
        qa_passed=job.qa_passed,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failure_kind=job.failure_kind,
        failure_message=job.failure_message,
        created_at=job.created_at or datetime.now(UTC),
        master_asset=master_asset_resp,
        mockup_assets=mockup_resps,
        mockup_urls=mockup_urls,
    )


@router.post(
    "/{workflow_id}/production",
    response_model=ProductionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger the PNG Production Pipeline for an approved Gate 2 artwork asset",
)
async def trigger_production(
    workflow_id: uuid.UUID,
    payload: StartProductionRequest,
    user: CurrentUser,
    uow: UowDep,
) -> ProductionJobResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    job = await start_production_job(
        uow,
        workflow_id=workflow_id,
        owner_id=user.id,
        actor=user.email,
        force_new=payload.force_new,
        candidate_asset_id=payload.candidate_asset_id,
    )
    await uow.commit()

    settings = get_settings()
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    return await to_production_job_response(job, storage, uow)


@router.get(
    "/{workflow_id}/production-jobs",
    response_model=list[ProductionJobResponse],
    summary="List all production jobs for this workflow",
)
async def list_production_jobs(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
) -> list[ProductionJobResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    settings = get_settings()
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    jobs = await uow.production_jobs.list_for_workflow(workflow_id)
    responses = []
    for job in jobs:
        resp = await to_production_job_response(job, storage, uow)
        responses.append(resp)
    return responses


@router.get(
    "/{workflow_id}/production",
    response_model=ProductionJobResponse | None,
    summary="Get current or latest production job for this workflow",
)
async def get_latest_production(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
) -> ProductionJobResponse | None:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    latest_job = await uow.production_jobs.get_latest_for_workflow(workflow_id)
    if latest_job is None:
        return None

    settings = get_settings()
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    return await to_production_job_response(latest_job, storage, uow)


@router.patch(
    "/{workflow_id}/mockups/{asset_id}/cover",
    response_model=AssetResponse,
    summary="Set a generated mockup as the primary listing cover image",
)
async def set_mockup_cover_endpoint(
    workflow_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> AssetResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No workflow with that ID"
        )

    all_assets = await uow.assets.list_for_workflow(workflow_id)
    target_asset = next((a for a in all_assets if a.id == asset_id), None)
    if not target_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mockup asset not found")

    for a in all_assets:
        if (
            a.provenance and a.provenance.get("asset_type") == "mockup"
        ) or "/mockups/" in a.storage_key:
            if a.id == asset_id:
                a.provenance = dict(a.provenance or {}, is_cover=True)
            elif a.provenance and a.provenance.get("is_cover"):
                a.provenance = dict(a.provenance, is_cover=False)
            await uow.session.flush()

    await uow.commit()
    url = await storage.signed_url(target_asset.storage_key, 86400 * 7)
    return to_asset_response(target_asset, url)


@router.patch(
    "/{workflow_id}/mockups/reorder",
    response_model=list[AssetResponse],
    summary="Reorder listing mockup assets",
)
async def reorder_mockups_endpoint(
    workflow_id: uuid.UUID,
    payload: ReorderMockupsRequest,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> list[AssetResponse]:

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No workflow with that ID"
        )

    all_assets = await uow.assets.list_for_workflow(workflow_id)
    asset_map = {a.id: a for a in all_assets}

    for idx, aid in enumerate(payload.asset_ids, start=1):
        if aid in asset_map:
            asset = asset_map[aid]
            asset.provenance = dict(asset.provenance or {}, listing_order=idx)
            await uow.session.flush()

    await uow.commit()

    refreshed_assets = await uow.assets.list_for_workflow(workflow_id)
    mockups = [
        a
        for a in refreshed_assets
        if (a.provenance and a.provenance.get("asset_type") == "mockup")
        or "/mockups/" in a.storage_key
    ]

    def _order_key(a: Asset) -> tuple[int, int, datetime]:
        is_cov = bool(a.provenance.get("is_cover", False)) if a.provenance else False
        order = int(str(a.provenance.get("listing_order", 999) or 999)) if a.provenance else 999
        return (order, 0 if is_cov else 1, a.created_at or datetime.min)

    sorted_mockups = sorted(mockups, key=_order_key)
    resps = []
    for m in sorted_mockups:
        url = await storage.signed_url(m.storage_key, 86400 * 7)
        resps.append(to_asset_response(m, url))
    return resps


@router.delete(
    "/{workflow_id}/mockups/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a generated mockup asset safely",
)
async def delete_mockup_endpoint(
    workflow_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> Response:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No workflow with that ID"
        )

    all_assets = await uow.assets.list_for_workflow(workflow_id)
    target_asset = next((a for a in all_assets if a.id == asset_id), None)
    if not target_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mockup asset not found")

    was_cover = (
        bool(target_asset.provenance.get("is_cover", False)) if target_asset.provenance else False
    )

    # Delete storage object in S3
    import contextlib

    with contextlib.suppress(Exception):
        await storage.delete(target_asset.storage_key)

    # Delete asset in DB
    await uow.assets.delete(target_asset)
    await uow.session.flush()

    # If it was cover, elect first remaining mockup as cover
    if was_cover:
        remaining_mockups = [
            a
            for a in all_assets
            if a.id != asset_id
            and (
                (a.provenance and a.provenance.get("asset_type") == "mockup")
                or "/mockups/" in a.storage_key
            )
        ]
        if remaining_mockups:
            remaining_mockups[0].provenance = dict(
                remaining_mockups[0].provenance or {}, is_cover=True
            )
            await uow.session.flush()

    await uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workflow_id}/mockups/recomposite-all",
    summary="Recomposite all existing workflow mockups with the current master PNG",
    response_model=list[AssetResponse],
)
async def recomposite_all_mockups_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> list[AssetResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No workflow with that ID"
        )

    # Find active master PNG
    assets = await uow.assets.list_for_workflow(workflow_id)
    master_asset = next(
        (
            a
            for a in assets
            if (
                a.storage_key.endswith("/master.png")
                or (a.provenance and a.provenance.get("profile") == "etsy-png-standard")
            )
            and "/mockups/" not in a.storage_key
            and (not a.provenance or a.provenance.get("asset_type") != "mockup")
        ),
        None,
    )
    if not master_asset:
        # Check artwork candidate
        artwork_assets = [
            a
            for a in assets
            if a.artwork_job_id is not None
            and "/mockups/" not in a.storage_key
            and (not a.provenance or a.provenance.get("asset_type") != "mockup")
        ]
        if artwork_assets:
            master_asset = artwork_assets[0]

    if not master_asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No master PNG or artwork found to composite.",
        )

    master_bytes = await storage.get(master_asset.storage_key)

    await recomposite_workflow_mockups(
        uow=uow,
        storage=storage,
        workflow_id=workflow_id,
        master_bytes=master_bytes,
        master_asset_id=master_asset.id,
        owner_id=user.id,
        image_worker_url=settings.image_worker_url,
    )
    await uow.commit()

    refreshed_assets = await uow.assets.list_for_workflow(workflow_id)
    mockups = [
        a
        for a in refreshed_assets
        if (a.provenance and a.provenance.get("asset_type") == "mockup")
        or "/mockups/" in a.storage_key
    ]

    def _order_key(a: Asset) -> tuple[int, int, datetime]:
        is_cov = bool(a.provenance.get("is_cover", False)) if a.provenance else False
        order = int(str(a.provenance.get("listing_order", 999) or 999)) if a.provenance else 999
        return (order, 0 if is_cov else 1, a.created_at or datetime.min)

    sorted_mockups = sorted(mockups, key=_order_key)
    resps = []
    for m in sorted_mockups:
        url = await storage.signed_url(m.storage_key, 86400 * 7)
        resps.append(to_asset_response(m, url))
    return resps


class SuggestMockupProductsResponse(BaseModel):
    suggestions: list[str]


@router.post(
    "/{workflow_id}/mockups/suggest-ideas",
    response_model=SuggestMockupProductsResponse,
    summary="Generate on-demand AI mockup product ideas for this workflow design",
)
async def suggest_mockup_ideas_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    cipher: CipherDep,
    settings: SettingsDep,
) -> SuggestMockupProductsResponse:
    """Generate on-demand AI mockup product recommendations specifically for this concept."""
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    approved_concept = next(
        (c for c in concepts if c.status == ConceptStatus.APPROVED),
        concepts[0] if concepts else None,
    )

    slogan = None
    title = approved_concept.title if approved_concept else workflow.name
    concept_uses: list[str] = []
    if approved_concept:
        prompts = await uow.concepts.prompts(approved_concept.id)
        if prompts:
            slogan = prompts[0].exact_slogan
            concept_uses = prompts[0].intended_product_uses or []

    suggested_raw: list[str] = []
    try:
        from app.application.owner_settings import reveal_credential
        from app.domain.enums import ProviderName
        from app.ports.providers import TextRequest
        from app.providers.gemini import GeminiSynthesisAdapter
        from app.providers.openai import OpenAISynthesisAdapter

        gemini_key = None
        openai_key = None
        try:
            gemini_key = await reveal_credential(
                uow, user.id, provider=ProviderName.GEMINI, cipher=cipher
            )
        except Exception:
            gemini_key = None

        try:
            openai_key = await reveal_credential(
                uow, user.id, provider=ProviderName.OPENAI, cipher=cipher
            )
        except Exception:
            openai_key = None

        prompt_text = (
            f"You are an Etsy merchandising expert. Recommend 4-6 distinct, top-selling physical product types "
            f"for this graphic artwork:\n"
            f"Concept Title: {title}\n"
            f"Slogan: {slogan or 'Graphic Art'}\n"
            f"Current Products: {workflow.intended_product_uses}\n\n"
            f"Respond ONLY with a comma-separated list of product types (e.g. Graphic Crewneck Sweatshirt, Insulated Travel Mug, Die Cut Vinyl Decal, Canvas Tote Bag, Ceramic Mug, Soy Candle)."
        )

        if gemini_key:
            provider = GeminiSynthesisAdapter(api_key=gemini_key)
            resp = await provider.generate(TextRequest(prompt=prompt_text))
            if resp and resp.text:
                suggested_raw = _clean_product_suggestion_list(resp.text)
        elif openai_key:
            provider = OpenAISynthesisAdapter(api_key=openai_key)
            resp = await provider.generate(TextRequest(prompt=prompt_text))
            if resp and resp.text:
                suggested_raw = _clean_product_suggestion_list(resp.text)
        elif concept_uses:
            suggested_raw = _clean_product_suggestion_list(concept_uses)
        else:
            suggested_raw = [
                "Graphic Crewneck Sweatshirt",
                "Insulated Travel Mug",
                "Die Cut Vinyl Decal",
                "Canvas Tote Bag",
                "Wall Art Poster",
            ]
    except Exception:
        suggested_raw = _clean_product_suggestion_list(concept_uses) if concept_uses else [
            "Graphic Crewneck Sweatshirt",
            "Insulated Travel Mug",
            "Die Cut Vinyl Decal",
            "Canvas Tote Bag",
            "Wall Art Poster",
        ]

    cleaned = _clean_product_suggestion_list(suggested_raw)

    # Persist the newly generated ideas in the DB for this campaign / concept
    if approved_concept:
        from app.infrastructure.models.concept import DesignPrompt, ProductConcept

        concept_row = await uow.session.get(ProductConcept, approved_concept.id)
        if concept_row:
            concept_row.intended_product_uses = list(cleaned)
            uow.session.add(concept_row)

        if prompts:
            prompt_row = await uow.session.get(DesignPrompt, prompts[0].id)
            if prompt_row:
                prompt_row.intended_product_uses = list(cleaned)
                uow.session.add(prompt_row)

        await uow.commit()

    return SuggestMockupProductsResponse(suggestions=cleaned)


@router.put(
    "/{workflow_id}/mockups/suggested-products",
    response_model=SuggestMockupProductsResponse,
    summary="Update and persist suggested mockup product categories for this workflow in DB",
)
async def update_mockup_suggestions_endpoint(
    workflow_id: uuid.UUID,
    payload: UpdateMockupSuggestionsRequest,
    user: CurrentUser,
    uow: UowDep,
) -> SuggestMockupProductsResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    cleaned = _clean_product_suggestion_list(payload.suggestions)

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    approved_concept = next(
        (c for c in concepts if c.status == ConceptStatus.APPROVED),
        concepts[0] if concepts else None,
    )

    if approved_concept:
        from app.infrastructure.models.concept import DesignPrompt, ProductConcept

        concept_row = await uow.session.get(ProductConcept, approved_concept.id)
        if concept_row:
            concept_row.intended_product_uses = list(cleaned)
            uow.session.add(concept_row)

        prompts = await uow.concepts.prompts(approved_concept.id)
        if prompts:
            prompt_row = await uow.session.get(DesignPrompt, prompts[0].id)
            if prompt_row:
                prompt_row.intended_product_uses = list(cleaned)
                uow.session.add(prompt_row)

        await uow.commit()

    return SuggestMockupProductsResponse(suggestions=cleaned)


def _clean_product_suggestion_list(raw_input: Any) -> list[str]:
    """Parse JSON lists, comma-delimited strings, and strip quotes/brackets from LLM output."""
    import json
    import re

    if isinstance(raw_input, list):
        items = raw_input
    elif isinstance(raw_input, str):
        text = raw_input.strip()
        if "[" in text and "]" in text:
            try:
                start = text.index("[")
                end = text.rindex("]") + 1
                parsed = json.loads(text[start:end])
                if isinstance(parsed, list):
                    items = parsed
                else:
                    items = text.split(",")
            except Exception:
                items = text.split(",")
        else:
            items = text.replace("\n", ",").split(",")
    else:
        items = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item).strip()
        # Strip brackets, quotes, markdown formatting, bullets
        s = s.strip("[]\"'`*•-\t\r\n ")
        s = re.sub(r"^\d+[\.\)]\s*", "", s).strip("[]\"'` ")
        if s and 2 <= len(s) <= 50:
            norm = s.lower()
            if norm not in seen:
                seen.add(norm)
                cleaned.append(s)
    return cleaned[:6]


@router.post(
    "/{workflow_id}/mockup-templates/composite",
    summary="Composite master PNG onto custom mockup template (JSON or multipart)",
)
async def workflow_composite_mockup_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
    request: Request,
) -> Any:
    from app.api.routes.mockup_templates import (
        CompositeCustomMockupRequest,
        PlacementSchema,
        composite_custom_mockup_endpoint,
    )

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        product_type = str(form.get("product_type", "tshirt"))
        template_id = str(form.get("template_id")) if form.get("template_id") else None
        template_name = str(form.get("name")) if form.get("name") else None
        save_as_template = str(form.get("save_to_library", "true")).lower() in ("true", "1")
        target_asset_id_raw = form.get("target_asset_id")
        target_asset_id = uuid.UUID(str(target_asset_id_raw)) if target_asset_id_raw else None

        file_obj = form.get("file")
        template_image_base64 = None
        if file_obj and hasattr(file_obj, "read"):
            file_bytes = await file_obj.read()
            template_image_base64 = base64.b64encode(file_bytes).decode("utf-8")

        def _get_float(key: str, default: float) -> float:
            val = form.get(key)
            if val is None:
                return default
            try:
                return float(str(val))
            except (ValueError, TypeError):
                return default

        placement = PlacementSchema(
            left_pct=_get_float("left_pct", 0.25),
            top_pct=_get_float("top_pct", 0.25),
            width_pct=_get_float("width_pct", 0.50),
            height_pct=_get_float("height_pct", 0.50),
            angle_deg=_get_float("angle_deg", 0.0),
            blend_mode=str(form.get("blend_mode") or "multiply"),
        )
        payload = CompositeCustomMockupRequest(
            workflow_id=workflow_id,
            product_type=product_type,
            template_id=template_id,
            template_image_base64=template_image_base64,
            template_name=template_name,
            save_as_template=save_as_template,
            placement=placement,
            target_asset_id=target_asset_id,
        )
    else:
        body = await request.json()
        body["workflow_id"] = str(workflow_id)
        payload = CompositeCustomMockupRequest.model_validate(body)

    return await composite_custom_mockup_endpoint(
        payload=payload,
        user=user,
        uow=uow,
        storage=storage,
        settings=settings,
    )


# --------------------------------------------------------------------------
# Phase 8: Listing Draft, Trademark Screening & Gate 3 Review
# --------------------------------------------------------------------------


async def _build_listing_response(
    draft: Any,
    workflow_id: uuid.UUID,
    uow: UnitOfWork,
    storage: Any,
) -> ListingDraftResponse:
    assets = await uow.assets.list_for_workflow(workflow_id)
    sorted_assets = sorted(assets, key=lambda a: a.created_at or datetime.min, reverse=True)
    package_asset = next(
        (
            a
            for a in sorted_assets
            if (
                (a.provenance and a.provenance.get("kind") == "customer_package")
                or a.mime_type == "application/zip"
                or a.storage_key.endswith(".zip")
            )
        ),
        None,
    )
    pkg_url = None
    pkg_resp = None
    if package_asset:
        pkg_url = await storage.signed_url(package_asset.storage_key, 3600)
        pkg_resp = to_asset_response(package_asset, pkg_url)

    risk_val = (
        draft.ip_risk_level.value
        if hasattr(draft.ip_risk_level, "value")
        else str(draft.ip_risk_level)
    )
    raw_history = (draft.ip_findings or {}).get("history")
    history_list = list(raw_history) if isinstance(raw_history, list) else []

    raw_tag_history = (draft.ip_findings or {}).get("tag_history")
    tag_history_list: list[str] = (
        [str(t) for t in raw_tag_history if t]
        if isinstance(raw_tag_history, list)
        else []
    )
    seen_tags = set(tag_history_list)
    for t in draft.tags or []:
        clean = str(t).strip().lower()
        if clean and clean not in seen_tags:
            seen_tags.add(clean)
            tag_history_list.append(clean)
    for snap in history_list:
        for t in snap.get("tags", []):
            clean = str(t).strip().lower()
            if clean and clean not in seen_tags:
                seen_tags.add(clean)
                tag_history_list.append(clean)

    return ListingDraftResponse(
        id=draft.id,
        workflow_id=draft.workflow_id,
        title=draft.title,
        description=draft.description,
        tags=draft.tags,
        ai_disclosure=draft.ai_disclosure,
        licence_text=draft.licence_text,
        customer_instructions=draft.customer_instructions,
        ip_reviewed_phrase=draft.ip_reviewed_phrase,
        ip_risk_level=risk_val,
        ip_findings=draft.ip_findings or {},
        ip_acknowledged_at=draft.ip_acknowledged_at,
        ip_acknowledged_by=draft.ip_acknowledged_by,
        version=draft.version,
        package_asset=pkg_resp,
        package_download_url=pkg_url,
        history=history_list,
        tag_history=tag_history_list,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


async def _resolve_trademark_provider(
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    settings: Any,
) -> tuple[Any, Any | None, Any | None, str | None]:
    from app.domain.enums import ProviderName
    from app.providers.fake import FakeTrademarkSearchAdapter
    from app.providers.postgres_trademark import PostgresTrademarkSearchAdapter
    from app.providers.tsdr import UsptoTsdrAdapter

    db_provider = PostgresTrademarkSearchAdapter(uow)
    latest_dt = await uow.trademarks.get_latest_source_date()
    dataset_updated_at = latest_dt.isoformat() if latest_dt else None

    if settings.provider_mode == "live":
        tsdr_adapter: Any | None = None
        cred = await uow.credentials.get(owner_id, ProviderName.USPTO)
        if cred:
            from app.api.dependencies import build_credential_cipher

            cipher = build_credential_cipher(settings)
            if cipher:
                raw_key = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)
                tsdr_adapter = UsptoTsdrAdapter(api_key=raw_key)

        if tsdr_adapter is None and hasattr(settings, "uspto_api_key") and settings.uspto_api_key:
            tsdr_adapter = UsptoTsdrAdapter(api_key=settings.uspto_api_key.get_secret_value())

        return db_provider, None, tsdr_adapter, dataset_updated_at

    return FakeTrademarkSearchAdapter(), None, None, dataset_updated_at


@router.get(
    "/{workflow_id}/listing",
    response_model=ListingDraftResponse,
    summary="Get or initialize listing draft and customer package status",
)
async def get_listing_draft_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing_service = ListingDraftService()
    draft = await listing_service.get_or_create_listing(workflow_id, uow)
    await uow.commit()

    return await _build_listing_response(draft, workflow_id, uow, storage)


@router.put(
    "/{workflow_id}/listing",
    response_model=ListingDraftResponse,
    summary="Update listing title, description, and tags",
)
async def update_listing_draft_endpoint(
    workflow_id: uuid.UUID,
    payload: UpdateListingDraftRequest,
    user: CurrentUser,
    uow: UowDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.trademark import TrademarkScreeningService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
        await _resolve_trademark_provider(workflow.owner_id, uow, settings)
    )
    trademark_service = TrademarkScreeningService(
        primary_provider,
        fallback_provider=fallback_provider,
        tsdr_adapter=tsdr_adapter,
        dataset_updated_at=dataset_updated_at,
    )
    listing_service = ListingDraftService()
    try:
        updated_draft = await listing_service.update_listing_draft(
            workflow_id=workflow_id,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            expected_version=payload.expected_version,
            uow=uow,
            actor_email=user.email,
            trademark_service=trademark_service,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(updated_draft, workflow_id, uow, storage)


@router.post(
    "/{workflow_id}/listing/restore-version",
    response_model=ListingDraftResponse,
    summary="Restore listing copy from a previous version snapshot",
)
async def restore_listing_version_endpoint(
    workflow_id: uuid.UUID,
    payload: RestoreListingVersionRequest,
    user: CurrentUser,
    uow: UowDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.trademark import TrademarkScreeningService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
        await _resolve_trademark_provider(workflow.owner_id, uow, settings)
    )
    trademark_service = TrademarkScreeningService(
        primary_provider,
        fallback_provider=fallback_provider,
        tsdr_adapter=tsdr_adapter,
        dataset_updated_at=dataset_updated_at,
    )
    listing_service = ListingDraftService()
    try:
        updated_draft = await listing_service.restore_version(
            workflow_id=workflow_id,
            target_version=payload.version,
            uow=uow,
            actor_email=user.email,
            trademark_service=trademark_service,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(updated_draft, workflow_id, uow, storage)


@router.delete(
    "/{workflow_id}/listing/versions/{version_number}",
    response_model=ListingDraftResponse,
    summary="Delete a listing copy version from history",
)
async def delete_listing_version_endpoint(
    workflow_id: uuid.UUID,
    version_number: int,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing_service = ListingDraftService()
    try:
        updated_draft = await listing_service.delete_version(
            workflow_id=workflow_id,
            target_version=version_number,
            uow=uow,
            actor_email=user.email,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(updated_draft, workflow_id, uow, storage)


@router.delete(
    "/{workflow_id}/listing/tags/history/{tag}",
    response_model=ListingDraftResponse,
    summary="Delete a tag from campaign tag history",
)
async def delete_tag_from_history_endpoint(
    workflow_id: uuid.UUID,
    tag: str,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing_service = ListingDraftService()
    try:
        updated_draft = await listing_service.remove_tag_from_history(
            workflow_id=workflow_id,
            tag=tag,
            uow=uow,
            actor_email=user.email,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(updated_draft, workflow_id, uow, storage)


@router.post(
    "/{workflow_id}/listing/rescreen",
    response_model=ListingDraftResponse,
    summary="Re-screen existing listing draft terms against trademark database",
)
@router.post(
    "/{workflow_id}/listing/rescreen-trademark",
    response_model=ListingDraftResponse,
    summary="Re-screen existing listing draft terms against trademark database (alias)",
    include_in_schema=False,
)
async def rescreen_trademark_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.trademark import TrademarkScreeningService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
        await _resolve_trademark_provider(workflow.owner_id, uow, settings)
    )
    trademark_service = TrademarkScreeningService(
        primary_provider,
        fallback_provider=fallback_provider,
        tsdr_adapter=tsdr_adapter,
        dataset_updated_at=dataset_updated_at,
    )
    listing_service = ListingDraftService()

    try:
        updated_draft = await listing_service.rescreen_trademark(
            workflow_id=workflow_id,
            uow=uow,
            trademark_service=trademark_service,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(updated_draft, workflow_id, uow, storage)


@router.post(
    "/{workflow_id}/listing/generate-seo",
    response_model=ListingDraftResponse,
    summary="Generate AI SEO copy and run trademark screening",
)
async def generate_listing_seo_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.package import CustomerPackageService
    from app.application.seo import generate_listing_seo
    from app.application.trademark import TrademarkScreeningService
    from app.providers.fake import FakeTextProvider
    from app.providers.gemini import GeminiSynthesisAdapter

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    concepts = await uow.concepts.list_for_workflow(workflow_id)
    if not concepts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow has no product concept",
        )
    concept = concepts[0]

    prompts = await uow.concepts.prompts(concept.id)
    latest_prompt = prompts[-1] if prompts else None

    # Text provider resolution
    text_provider: Any = FakeTextProvider()
    if settings.provider_mode == "live":
        # Check for Gemini credentials
        cred = await uow.credentials.get(workflow.owner_id, ProviderName.GEMINI)
        if cred:
            from app.api.dependencies import build_credential_cipher

            cipher = build_credential_cipher(settings)
            if cipher:
                raw_key = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)
                text_provider = GeminiSynthesisAdapter(api_key=raw_key)

    # Keyword clusters from research
    research_runs = await uow.research.list_runs_for_workflow(workflow_id)
    keywords: list[str] = []
    for r in research_runs:
        clusters = await uow.research.get_keyword_clusters_for_run(r.id)
        for cl in clusters:
            keywords.append(cl.primary_phrase)
            keywords.extend(cl.attributes)

    try:
        seo_draft = await generate_listing_seo(
            concept=concept,
            prompt=latest_prompt,
            keywords=keywords[:15],
            text_provider=text_provider,
        )

        from app.application.listing import ListingDraftService, record_version_snapshot
        listing_service = ListingDraftService()
        draft = await listing_service.get_or_create_listing(workflow_id, uow)
        updated_draft = await uow.listing_drafts.update(
            draft.id,
            title=seo_draft.title,
            description=seo_draft.description,
            tags=seo_draft.tags,
            ai_disclosure=seo_draft.ai_disclosure,
        )

        # Trademark screen
        primary_provider, fallback_provider, tsdr_adapter, dataset_updated_at = (
            await _resolve_trademark_provider(workflow.owner_id, uow, settings)
        )
        trademark_service = TrademarkScreeningService(
            primary_provider,
            fallback_provider=fallback_provider,
            tsdr_adapter=tsdr_adapter,
            dataset_updated_at=dataset_updated_at,
        )
        screened_draft = await listing_service.rescreen_trademark(
            workflow_id=workflow_id,
            uow=uow,
            trademark_service=trademark_service,
        )
        record_version_snapshot(screened_draft, source="ai_generated")

        # Customer package
        package_service = CustomerPackageService(storage)
        try:
            await package_service.build_customer_package(workflow_id, uow)
        except Exception as pkg_err:
            # Package builder error shouldn't fail the SEO generation
            pass

        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SEO generation failed: {exc}",
        )

    return await _build_listing_response(screened_draft, workflow_id, uow, storage)


@router.post(
    "/{workflow_id}/listing/package",
    response_model=ListingDraftResponse,
    summary="Build and assemble customer ZIP download package (Zero LLM tokens)",
)
async def build_listing_package_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.package import CustomerPackageService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing_service = ListingDraftService()
    draft = await listing_service.get_or_create_listing(workflow_id, uow)

    package_service = CustomerPackageService(storage)
    try:
        await package_service.build_customer_package(workflow_id, uow)
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer package build failed: {exc}",
        )

    return await _build_listing_response(draft, workflow_id, uow, storage)


@router.post(
    "/{workflow_id}/gates/listing",
    response_model=ListingDraftResponse,
    summary="Submit Gate 3 human decision (Approve / Reject)",
)
async def decide_gate3_endpoint(
    workflow_id: uuid.UUID,
    payload: Gate3DecisionRequest,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ListingDraftResponse:
    from app.application.listing import ListingDraftService
    from app.application.package import CustomerPackageService

    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    package_service = CustomerPackageService(storage)
    listing_service = ListingDraftService()

    try:
        _, draft = await listing_service.decide_gate3(
            workflow_id=workflow_id,
            decision=payload.decision,
            acknowledged=payload.acknowledged,
            owner_email=user.email,
            uow=uow,
            package_service=package_service,
        )
        await uow.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await _build_listing_response(draft, workflow_id, uow, storage)
