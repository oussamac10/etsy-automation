from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.workflow import JobStatus
from app.infrastructure.models import MockupJob


class SqlMockupJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: MockupJob) -> MockupJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> MockupJob | None:
        return await self._session.get(MockupJob, job_id)

    async def get_by_production_and_product(
        self, production_job_id: uuid.UUID, product_type: str
    ) -> MockupJob | None:
        result = await self._session.execute(
            select(MockupJob).where(
                MockupJob.production_job_id == production_job_id,
                MockupJob.product_type == product_type,
            )
        )
        return result.scalars().first()

    async def list_for_production_job(self, production_job_id: uuid.UUID) -> Sequence[MockupJob]:
        result = await self._session.execute(
            select(MockupJob)
            .where(MockupJob.production_job_id == production_job_id)
            .order_by(MockupJob.created_at.asc())
        )
        return result.scalars().all()

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[MockupJob]:
        result = await self._session.execute(
            select(MockupJob)
            .where(MockupJob.workflow_id == workflow_id)
            .order_by(MockupJob.created_at.desc())
        )
        return result.scalars().all()

    async def update(
        self,
        job_id: uuid.UUID,
        *,
        status: JobStatus | None = None,
        external_task_id: str | None = None,
        output_asset_id: uuid.UUID | None = None,
        attempt_count: int | None = None,
        result_mockup_url: str | None = None,
        failure_kind: str | None = None,
        failure_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> MockupJob:
        job = await self.get(job_id)
        if job is None:
            raise ValueError(f"MockupJob {job_id} not found")

        if status is not None:
            job.status = status
        if external_task_id is not None:
            job.external_task_id = external_task_id
        if output_asset_id is not None:
            job.output_asset_id = output_asset_id
        if attempt_count is not None:
            job.attempt_count = attempt_count
        if result_mockup_url is not None:
            job.result_mockup_url = result_mockup_url
        if failure_kind is not None:
            job.failure_kind = failure_kind
        if failure_message is not None:
            job.failure_message = failure_message
        if completed_at is not None:
            job.completed_at = completed_at

        await self._session.flush()
        return job
