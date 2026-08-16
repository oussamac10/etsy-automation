from __future__ import annotations

import uuid

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import EntityNotFoundError
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    FailureStatus,
    GateNotApprovedError,
    IllegalTransitionError,
    JobStatus,
    RunStatus,
)
from app.infrastructure.models import Asset, ProductionJob


async def get_approved_artwork_asset(
    uow: UnitOfWork, workflow_id: uuid.UUID
) -> Asset:
    """Resolve the Gate 2 approved artwork Asset for this workflow."""
    approvals = await uow.approvals.history(workflow_id, gate=ApprovalGate.ARTWORK_APPROVAL)
    gate2_approval = next(
        (
            a
            for a in approvals
            if a.decision == ApprovalDecision.APPROVED
        ),
        None,
    )

    if gate2_approval and gate2_approval.target_id:
        target_asset = await uow.assets.get(gate2_approval.target_id)
        if target_asset:
            return target_asset

    # Find the approved asset among workflow assets
    assets = await uow.assets.list_for_workflow(workflow_id)
    artwork_assets = [a for a in assets if a.artwork_job_id is not None]
    if not artwork_assets:
        artwork_assets = [a for a in assets if not a.storage_key.startswith("production/")]

    if not artwork_assets:
        raise EntityNotFoundError("Asset", workflow_id)

    return artwork_assets[0]


async def start_production_job(
    uow: UnitOfWork,
    *,
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    actor: str,
    force_new: bool = False,
    candidate_asset_id: uuid.UUID | None = None,
) -> ProductionJob:
    """Validate Gate 2 approval and start a deterministic PNG production job."""
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != owner_id:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    gate2_approved = await uow.approvals.is_approved(workflow_id, ApprovalGate.ARTWORK_APPROVAL)

    allowed_states = {
        RunStatus.ART_REVIEW,
        RunStatus.ARTWORK_APPROVED,
        RunStatus.PRODUCTION,
        FailureStatus.PRODUCTION_FAILED,
        RunStatus.CANCELLED,
    }

    if not gate2_approved and workflow.state not in (RunStatus.ARTWORK_APPROVED, RunStatus.ART_REVIEW):
        raise GateNotApprovedError(
            gate=ApprovalGate.ARTWORK_APPROVAL,
            current=workflow.state,
            action="PNG production",
        )

    if workflow.state not in allowed_states:
        raise IllegalTransitionError(
            current=workflow.state,
            requested=RunStatus.PRODUCTION,
            reason="PNG production requires Gate 2 approval and ARTWORK_APPROVED state",
        )

    if candidate_asset_id is not None:
        target_asset = await uow.assets.get(candidate_asset_id)
        if target_asset and target_asset.workflow_id == workflow_id:
            source_asset = target_asset
            await uow.approvals.record(
                workflow=workflow,
                gate=ApprovalGate.ARTWORK_APPROVAL,
                decision=ApprovalDecision.APPROVED,
                previous_state=workflow.state,
                resulting_state=RunStatus.ARTWORK_APPROVED,
                actor=actor,
                target_type="Asset",
                target_id=source_asset.id,
            )
        else:
            source_asset = await get_approved_artwork_asset(uow, workflow_id)
    else:
        source_asset = await get_approved_artwork_asset(uow, workflow_id)

    latest_job = await uow.production_jobs.get_latest_for_workflow(workflow_id)
    # If not forcing new and either candidate_asset_id is omitted or matches existing job's source_asset_id, return existing job
    if latest_job is not None and not force_new and (candidate_asset_id is None or latest_job.source_asset_id == source_asset.id):
        if latest_job.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED):
            # Ensure outbox task exists if queued
            if latest_job.status == JobStatus.QUEUED:
                await uow.outbox.add(
                    "run_production_task",
                    {
                        "workflow_id": str(workflow_id),
                        "production_job_id": str(latest_job.id),
                    },
                )
            return latest_job

    idempotency_key = f"prod-{workflow_id}-{source_asset.id}-{uuid.uuid4().hex[:8]}"
    job = ProductionJob(
        workflow_id=workflow_id,
        source_asset_id=source_asset.id,
        operations=["trim_and_pad", "upscale", "typography", "qa", "mockup"],
        status=JobStatus.QUEUED,
        idempotency_key=idempotency_key,
        attempt_count=0,
        qa_report={},
    )
    await uow.production_jobs.add(job)

    if workflow.state != RunStatus.PRODUCTION:
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.PRODUCTION,
            expected_version=workflow.version,
            reason="Started PNG production pipeline",
            actor=actor,
        )

    await uow.outbox.add(
        "run_production_task",
        {
            "workflow_id": str(workflow_id),
            "production_job_id": str(job.id),
        },
    )

    return job
