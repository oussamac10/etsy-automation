from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.application.production import start_production_job
from app.domain.workflow import (
    ApprovalGate,
    GateNotApprovedError,
    IllegalTransitionError,
    JobStatus,
    RunStatus,
)
from app.infrastructure.models import Asset, ProductionJob, ProductWorkflow


class TestProductionUnit:
    @pytest.mark.asyncio
    async def test_start_production_fails_when_gate_2_not_approved(self) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.DRAFT

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.approvals.is_approved = AsyncMock(return_value=False)

        with pytest.raises(GateNotApprovedError):
            await start_production_job(
                uow,
                workflow_id=workflow_id,
                owner_id=owner_id,
                actor="test@example.com",
            )

    @pytest.mark.asyncio
    async def test_start_production_happy_path(self) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        source_asset_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ARTWORK_APPROVED
        workflow.version = 5

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.approvals.is_approved = AsyncMock(return_value=True)
        uow.approvals.history = AsyncMock(return_value=[])

        source_asset = MagicMock(spec=Asset)
        source_asset.id = source_asset_id
        source_asset.artwork_job_id = uuid.uuid4()
        source_asset.storage_key = "assets/test.png"

        uow.assets.list_for_workflow = AsyncMock(return_value=[source_asset])
        uow.production_jobs.get_latest_for_workflow = AsyncMock(return_value=None)
        uow.production_jobs.add = AsyncMock()
        uow.workflows.transition = AsyncMock()
        uow.outbox.add = AsyncMock()

        job = await start_production_job(
            uow,
            workflow_id=workflow_id,
            owner_id=owner_id,
            actor="test@example.com",
        )

        assert job.status == JobStatus.QUEUED
        assert job.source_asset_id == source_asset_id
        uow.production_jobs.add.assert_called_once()
        uow.workflows.transition.assert_called_once_with(
            workflow,
            to_state=RunStatus.PRODUCTION,
            expected_version=5,
            reason="Started PNG production pipeline",
            actor="test@example.com",
        )
        uow.outbox.add.assert_called_once_with(
            "run_production_task",
            {"workflow_id": str(workflow_id), "production_job_id": str(job.id)},
        )

    @pytest.mark.asyncio
    async def test_start_production_idempotent_when_already_queued(self) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.PRODUCTION

        existing_job = MagicMock(spec=ProductionJob)
        existing_job.id = uuid.uuid4()
        existing_job.status = JobStatus.QUEUED

        source_asset = MagicMock(spec=Asset)
        source_asset.id = uuid.uuid4()
        source_asset.artwork_job_id = uuid.uuid4()

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.approvals.is_approved = AsyncMock(return_value=True)
        uow.approvals.history = AsyncMock(return_value=[])
        uow.assets.list_for_workflow = AsyncMock(return_value=[source_asset])
        uow.production_jobs.get_latest_for_workflow = AsyncMock(return_value=existing_job)
        uow.outbox.add = AsyncMock()

        job = await start_production_job(
            uow,
            workflow_id=workflow_id,
            owner_id=owner_id,
            actor="test@example.com",
            force_new=False,
        )

        assert job == existing_job
        uow.outbox.add.assert_called_once_with(
            "run_production_task",
            {"workflow_id": str(workflow_id), "production_job_id": str(existing_job.id)},
        )
