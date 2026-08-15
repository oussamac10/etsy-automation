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
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from app.api.dependencies import CurrentUser, SettingsDep, StorageDep, UowDep
from app.api.schemas import (
    ApprovalResponse,
    ArtworkJobResponse,
    AssetResponse,
    ConceptRevisionRequest,
    CreateWorkflowRequest,
    DesignPromptResponse,
    GateDecisionRequest,
    GenerateArtworkRequest,
    OriginalIdeaResponse,
    ProductConceptResponse,
    ProductionJobResponse,
    RefineArtworkRequest,
    ResearchRunResponse,
    StartProductionRequest,
    SubmitIdeaRequest,
    TimelineEntryResponse,
    TimelineResponse,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.application import workflows as use_cases
from app.application.artwork import ensure_artwork_within_budget, estimate_artwork_cost
from app.application.production import start_production_job
from app.application.research import queue_research_run
from app.application.unit_of_work import UnitOfWork
from app.domain import ip_risk
from app.domain.enums import ConceptStatus, ProviderName
from app.domain.workflow import RiskLevel, RunStatus, JobStatus
from app.infrastructure.models import ArtworkJob, Asset, ProductionJob
from app.providers.s3 import S3ObjectStorage
from app.settings import get_settings

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
    workflow = await use_cases.cancel_workflow(
        uow, workflow_id, owner_id=user.id, actor=user.email
    )
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
    await uow.commit()

    return DesignPromptResponse.model_validate(prompt)


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
        created_at=asset.created_at,
        url=url,
    )


def to_job_response(job: ArtworkJob, assets: list[AssetResponse] = []) -> ArtworkJobResponse:
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
        assets=assets,
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

    if workflow.state not in (RunStatus.IDEA_APPROVED, "ART_GENERATION_FAILED", RunStatus.ART_REVIEW):
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

    idempotency_key = (
        f"art-{workflow_id}-{latest_prompt.id}-{candidate_count}-{provider_val}-{model_val}"
        if not force_new
        else f"art-{workflow_id}-{latest_prompt.id}-{candidate_count}-{provider_val}-{model_val}-{uuid.uuid4().hex[:8]}"
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

    if workflow.state not in (RunStatus.ART_REVIEW, "ART_GENERATION_FAILED", RunStatus.ARTWORK_APPROVED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot regenerate artwork unless artwork was already generated or failed.",
        )

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
    latest_prompt = prompts[-1]

    refined_prompt = await uow.concepts.add_prompt_version(
        approved_concept,
        positive_prompt=payload.positive_prompt,
        negative_prompt=payload.negative_prompt or latest_prompt.negative_prompt,
        typography_instructions=latest_prompt.typography_instructions,
        exact_slogan=latest_prompt.exact_slogan,
        change_note=payload.change_note,
        generation_metadata={"reference_asset_id": str(payload.candidate_asset_id)},
    )

    settings = get_settings()
    provider_val = "gemini"
    model_val = "gemini-3.1-flash-image"
    provider_enum = ProviderName.GEMINI
    candidate_count = 1

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
        target_version=None,
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

    mockup_jobs = await uow.mockup_jobs.list_for_production_job(job.id)
    mockup_resps: list[AssetResponse] = []
    mockup_urls: dict[str, str] = {}

    if mockup_jobs:
        for mj in mockup_jobs:
            if mj.output_asset_id is not None:
                asset = await uow.assets.get(mj.output_asset_id)
                if asset is not None:
                    url = await storage.signed_url(asset.storage_key, 3600)
                    mockup_resps.append(to_asset_response(asset, url))
                    p_name = str(mj.product_type).lower()
                    if "sweat" in p_name or "hoodie" in p_name or "jumper" in p_name:
                        mockup_urls["sweatshirt"] = url
                    elif "tshirt" in p_name or "t-shirt" in p_name or "tee" in p_name or p_name == "shirt" or "apparel" in p_name or ("shirt" in p_name and "sweat" not in p_name):
                        mockup_urls["tshirt"] = url
                    elif "mug" in p_name or "cup" in p_name:
                        mockup_urls["mug"] = url
                    elif "tote" in p_name or "bag" in p_name:
                        mockup_urls["tote"] = url
                        mockup_urls["tote_bag"] = url
                    mockup_urls[str(mj.product_type)] = url

    if not mockup_urls:
        assets = await uow.assets.list_for_workflow(job.workflow_id)
        job_mockups = [
            a
            for a in assets
            if a.storage_key.startswith(f"production/{job.workflow_id}/{job.id}/mockups/")
            or (a.provenance and a.provenance.get("production_job_id") == str(job.id))
        ]
        if not job_mockups:
            job_mockups = [
                a
                for a in assets
                if (job.output_asset_id is not None and a.derived_from_id == job.output_asset_id and (a.provenance.get("pipeline") == "mockup" or a.provenance.get("asset_type") == "mockup"))
            ]
        for asset in job_mockups:
            url = await storage.signed_url(asset.storage_key, 3600)
            mockup_resps.append(to_asset_response(asset, url))
            product_type = asset.provenance.get("product_type") if asset.provenance else None
            if not product_type:
                parts = asset.storage_key.split("/")
                if "mockups" in parts:
                    m_idx = parts.index("mockups")
                    if len(parts) > m_idx + 1:
                        product_type = parts[m_idx + 1].replace(".png", "").replace(".jpg", "")
                if not product_type:
                    product_type = asset.storage_key.rsplit("/", 1)[-1].replace(".png", "").replace(".jpg", "")

            p_name = str(product_type).lower()
            if "sweat" in p_name or "hoodie" in p_name or "jumper" in p_name:
                mockup_urls["sweatshirt"] = url
            elif "tshirt" in p_name or "t-shirt" in p_name or "tee" in p_name or p_name == "shirt" or "apparel" in p_name or ("shirt" in p_name and "sweat" not in p_name):
                mockup_urls["tshirt"] = url
            elif "mug" in p_name or "cup" in p_name:
                mockup_urls["mug"] = url
            elif "tote" in p_name or "bag" in p_name:
                mockup_urls["tote"] = url
                mockup_urls["tote_bag"] = url

            mockup_urls[str(product_type)] = url

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
        created_at=job.created_at,
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
):
    from app.api.routes.mockup_templates import (
        CompositeCustomMockupRequest,
        CompositeMockupResponse,
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
        )
    else:
        body = await request.json()
        body["workflow_id"] = str(workflow_id)
        payload = CompositeCustomMockupRequest.model_validate(body)

    return await composite_custom_mockup_endpoint(
        payload=payload,
        uow=uow,
        storage=storage,
        settings=settings,
    )



