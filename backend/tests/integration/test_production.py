from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.application.production import start_production_job
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import IdeaMode
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    GateNotApprovedError,
    JobStatus,
    RunStatus,
)
from app.infrastructure.models import (
    Asset,
)

pytestmark = pytest.mark.integration


async def _create_test_workflow(uow: UnitOfWork, owner_id: uuid.UUID) -> uuid.UUID:
    from app.application.workflows import CreateWorkflowCommand, create_workflow

    workflow = await create_workflow(
        uow,
        CreateWorkflowCommand(
            owner_id=owner_id,
            idea_mode=IdeaMode.MARKET_LED,
            name="Production Test Workflow",
            target_country="US",
            output_language="en",
        ),
    )
    return workflow.id


class TestProductionPipeline:
    async def test_production_requires_gate_2_approval(
        self, uow: UnitOfWork, accounts: dict[str, uuid.UUID]
    ) -> None:
        owner_id = accounts["owner"]
        workflow_id = await _create_test_workflow(uow, owner_id)

        # Attempt to start production from DRAFT without Gate 2 approval
        with pytest.raises(GateNotApprovedError):
            await start_production_job(
                uow,
                workflow_id=workflow_id,
                owner_id=owner_id,
                actor="test@example.com",
            )

    async def test_production_job_creation_and_idempotency(
        self, uow: UnitOfWork, accounts: dict[str, uuid.UUID]
    ) -> None:
        owner_id = accounts["owner"]
        workflow_id = await _create_test_workflow(uow, owner_id)

        workflow = await uow.workflows.get(workflow_id)
        assert workflow is not None
        workflow.state = RunStatus.ARTWORK_APPROVED
        await uow.commit()

        # Add approved Gate 2 record
        await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.ARTWORK_APPROVAL,
            decision=ApprovalDecision.APPROVED,
            previous_state=RunStatus.ART_REVIEW,
            resulting_state=RunStatus.ARTWORK_APPROVED,
            actor="test@example.com",
            target_type="Asset",
        )

        # Add candidate asset
        asset = Asset(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            artwork_job_id=None,
            storage_key=f"assets/{workflow_id}/approved.png",
            mime_type="image/png",
            byte_size=1024,
            checksum_sha256="a" * 64,
            width=1024,
            height=1024,
            has_alpha=True,
            has_transparent_pixels=True,
            quality_check={},
            provenance={"generator": "recraft"},
        )
        await uow.assets.add(asset)
        await uow.commit()

        # Start production
        job1 = await start_production_job(
            uow,
            workflow_id=workflow_id,
            owner_id=owner_id,
            actor="test@example.com",
        )
        assert job1.status == JobStatus.QUEUED
        assert job1.source_asset_id == asset.id
        assert job1.workflow_id == workflow_id

        # Idempotent re-run without force_new returns same job
        job2 = await start_production_job(
            uow,
            workflow_id=workflow_id,
            owner_id=owner_id,
            actor="test@example.com",
            force_new=False,
        )
        assert job2.id == job1.id

    async def test_production_api_routes(
        self, client: httpx.AsyncClient, uow: UnitOfWork, accounts: dict[str, uuid.UUID]
    ) -> None:
        owner_id = accounts["owner"]
        workflow_id = await _create_test_workflow(uow, owner_id)

        workflow = await uow.workflows.get(workflow_id)
        assert workflow is not None
        workflow.state = RunStatus.ARTWORK_APPROVED
        await uow.commit()

        # Add Gate 2 approval
        await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.ARTWORK_APPROVAL,
            decision=ApprovalDecision.APPROVED,
            previous_state=RunStatus.ART_REVIEW,
            resulting_state=RunStatus.ARTWORK_APPROVED,
            actor="owner@example.com",
            target_type="Asset",
        )

        # Add approved asset
        asset = Asset(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            artwork_job_id=None,
            storage_key=f"assets/{workflow_id}/approved.png",
            mime_type="image/png",
            byte_size=2048,
            checksum_sha256="b" * 64,
            width=1024,
            height=1024,
            has_alpha=True,
            has_transparent_pixels=True,
            quality_check={},
            provenance={"generator": "gemini"},
        )
        await uow.assets.add(asset)
        await uow.commit()

        # Mock S3 storage signed_url
        with patch(
            "app.providers.s3.S3ObjectStorage.signed_url",
            new=AsyncMock(return_value="https://s3.example.com/asset.png"),
        ):
            # 1. Trigger production
            res = await client.post(
                f"/api/v1/workflows/{workflow_id}/production",
                json={"force_new": False},
            )
            assert res.status_code == 202
            body = res.json()
            assert body["workflow_id"] == str(workflow_id)
            assert body["status"] in ("QUEUED", "RUNNING", "SUCCEEDED")

            # 2. Get latest production
            res_latest = await client.get(f"/api/v1/workflows/{workflow_id}/production")
            assert res_latest.status_code == 200
            latest_body = res_latest.json()
            assert latest_body["id"] == body["id"]

            # 3. List production jobs
            res_jobs = await client.get(f"/api/v1/workflows/{workflow_id}/production-jobs")
            assert res_jobs.status_code == 200
            jobs_list = res_jobs.json()
            assert len(jobs_list) >= 1
            assert jobs_list[0]["id"] == body["id"]
