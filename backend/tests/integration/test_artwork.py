from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.application.artwork import ensure_artwork_within_budget, estimate_artwork_cost
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, ConceptStatus, IdeaMode, Seasonality
from app.domain.errors import BudgetExceededError
from app.domain.workflow import JobStatus, RunStatus
from app.infrastructure.models import ProductConcept, User

pytestmark = pytest.mark.integration


async def _workflow_for(uow: UnitOfWork, owner_id: uuid.UUID) -> uuid.UUID:
    from app.application.workflows import CreateWorkflowCommand, create_workflow

    workflow = await create_workflow(
        uow,
        CreateWorkflowCommand(
            owner_id=owner_id,
            idea_mode=IdeaMode.MARKET_LED,
            name="Artwork test workflow",
            target_country="US",
            output_language="en",
        ),
    )
    return workflow.id


class TestArtworkLogic:
    def test_estimate_cost(self) -> None:
        cost_fake = estimate_artwork_cost(
            provider="recraft",
            model="recraftv4_1",
            candidate_count=4,
            currency="USD",
            provider_mode="fake",
        )
        assert cost_fake.to_decimal() == Decimal("0.0")

        cost_live = estimate_artwork_cost(
            provider="recraft",
            model="recraftv4_1",
            candidate_count=4,
            currency="USD",
            provider_mode="live",
        )
        assert cost_live.to_decimal() > Decimal("0.0")

    async def test_artwork_budget_limit(self, uow: UnitOfWork, owner: User) -> None:
        settings = await uow.owner_settings.create_defaults(owner.id)
        settings.daily_budget_minor = 0
        settings.monthly_budget_minor = 0
        await uow.commit()

        # Fake mode should pass even with 0 budget
        await ensure_artwork_within_budget(
            uow,
            owner_id=owner.id,
            provider="recraft",
            model="recraftv4_1",
            candidate_count=4,
            provider_mode="fake",
        )

        # Live mode should raise BudgetExceededError on 0 budget
        with pytest.raises(BudgetExceededError):
            await ensure_artwork_within_budget(
                uow,
                owner_id=owner.id,
                provider="recraft",
                model="recraftv4_1",
                candidate_count=4,
                provider_mode="live",
            )

    async def test_artwork_api_flow(
        self, client: httpx.AsyncClient, uow: UnitOfWork, accounts: dict[str, uuid.UUID]
    ) -> None:
        owner_id = accounts["owner"]
        # Create a workflow
        workflow_id = await _workflow_for(uow, owner_id)

        # Set state directly to IDEA_APPROVED
        workflow = await uow.workflows.get(workflow_id)
        assert workflow is not None
        workflow.state = RunStatus.IDEA_APPROVED
        await uow.commit()

        # Add approved concept and design prompt
        concept = ProductConcept(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            title="Artwork Concept",
            description="Concept for test",
            origin=ConceptOrigin.MARKET,
            differentiation="test",
            seasonality=Seasonality.EVERGREEN,
            risk_level="low",
            score=4.5,
            score_breakdown={},
            status=ConceptStatus.APPROVED,
        )
        assert uow._session is not None
        uow._session.add(concept)
        await uow.commit()

        _prompt = await uow.concepts.add_prompt_version(
            concept,
            positive_prompt="A beautiful transparent PNG graphics of a cat",
            negative_prompt="blurry",
            typography_instructions=None,
            exact_slogan=None,
            change_note="Initial prompt",
        )
        await uow.commit()

        # 1. Trigger artwork generation
        resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/artwork",
            json={
                "provider": "recraft",
                "provider_model": "recraftv4_1",
                "requested_width": 1024,
                "requested_height": 1024,
                "quality": "standard",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "QUEUED"

        job_id = uuid.UUID(data["id"])

        # Check repository queries
        jobs = await uow.artwork_jobs.list_for_workflow(workflow_id)
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.QUEUED

        # 2. Test get list of artwork jobs
        resp = await client.get(f"/api/v1/workflows/{workflow_id}/artwork-jobs")
        assert resp.status_code == 200
        jobs_list = resp.json()
        assert len(jobs_list) == 1
        assert jobs_list[0]["id"] == str(job_id)

        # 3. Simulate Worker processing and S3 Mocking
        from worker.tasks import _run_artwork_async

        # Patch actual storage operations so it doesn't contact real S3
        with patch("app.providers.s3.boto3.client") as mock_boto_client:
            mock_client = mock_boto_client.return_value
            mock_client.put_object.return_value = {}
            mock_client.generate_presigned_url.return_value = "https://s3.stub/signed-url"

            await _run_artwork_async(workflow_id, job_id)

        # Verify job and workflow transitioned
        assert uow._session is not None
        uow._session.expire_all()
        job = await uow.artwork_jobs.get(job_id)
        assert job is not None
        assert job.status == JobStatus.SUCCEEDED

        wf = await uow.workflows.get(workflow_id)
        assert wf is not None
        assert wf.state == RunStatus.ART_REVIEW

        # Previews list should now return candidates with signed URLs
        resp = await client.get(f"/api/v1/workflows/{workflow_id}/artwork-jobs")
        assert resp.status_code == 200
        jobs_list = resp.json()
        assert len(jobs_list[0]["assets"]) == 4
        assert "http" in jobs_list[0]["assets"][0]["url"]

        asset_id = jobs_list[0]["assets"][0]["id"]

        # 4. Refinement endpoint
        resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/artwork/refine",
            json={
                "candidate_asset_id": asset_id,
                "positive_prompt": "Refined cat illustration",
                "negative_prompt": "blurry",
                "change_note": "Make it cleaner",
            },
        )
        assert resp.status_code == 201, f"Status: {resp.status_code}, Body: {resp.json()}"
        refine_data = resp.json()
        assert refine_data["status"] == "QUEUED"
        assert refine_data["provider"] == "recraft"

        refine_job_id = uuid.UUID(refine_data["id"])

        # Simulate worker on refinement
        with patch("app.providers.s3.boto3.client") as mock_boto_client:
            mock_client = mock_boto_client.return_value
            mock_client.put_object.return_value = {}
            mock_client.generate_presigned_url.return_value = "https://s3.stub/signed-url-refined"

            # Mock S3 get for reference image retrieval
            mock_s3_body = MagicMock()
            mock_s3_body.read = MagicMock(return_value=b"fake-bytes")

            # Since boto3 calls are in executors, stub get_object
            mock_client.get_object.return_value = {"Body": mock_s3_body, "ContentType": "image/png"}

            await _run_artwork_async(workflow_id, refine_job_id)

        # Verify refined job succeeded
        assert uow._session is not None
        uow._session.expire_all()
        refine_job = await uow.artwork_jobs.get(refine_job_id)
        assert refine_job is not None
        assert refine_job.status == JobStatus.SUCCEEDED

        # 5. Gate 2 Approval decision endpoint
        resp = await client.get(f"/api/v1/workflows/{workflow_id}/artwork-jobs")
        assert resp.status_code == 200
        _all_jobs = resp.json()

        # Approve Gate 2 using the generated asset
        resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": "ARTWORK_APPROVAL",
                "decision": "APPROVED",
                "target_type": "Asset",
                "target_id": str(asset_id),
                "target_version": None,
                "comment": "Perfect design!",
            },
        )
        assert resp.status_code == 201

        # Verify workflow is in ARTWORK_APPROVED state
        assert uow._session is not None
        uow._session.expire_all()
        wf = await uow.workflows.get(workflow_id)
        assert wf is not None
        assert wf.state == RunStatus.ARTWORK_APPROVED
