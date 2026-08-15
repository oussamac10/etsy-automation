from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import ProductionJob


class SqlProductionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: ProductionJob) -> ProductionJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> ProductionJob | None:
        return await self._session.get(ProductionJob, job_id)

    async def get_by_idempotency_key(self, key: str) -> ProductionJob | None:
        result = await self._session.execute(
            select(ProductionJob).where(ProductionJob.idempotency_key == key)
        )
        return result.scalars().first()

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ProductionJob]:
        result = await self._session.execute(
            select(ProductionJob)
            .where(ProductionJob.workflow_id == workflow_id)
            .order_by(ProductionJob.created_at.desc())
        )
        return result.scalars().all()

    async def get_latest_for_workflow(self, workflow_id: uuid.UUID) -> ProductionJob | None:
        result = await self._session.execute(
            select(ProductionJob)
            .where(ProductionJob.workflow_id == workflow_id)
            .order_by(ProductionJob.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def update(
        self,
        job_id: uuid.UUID,
        *,
        status: object,
        output_asset_id: uuid.UUID | None = None,
        operations: list[str] | None = None,
        attempt_count: int | None = None,
        qa_report: dict[str, object] | None = None,
        qa_passed: bool | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_kind: str | None = None,
        failure_message: str | None = None,
    ) -> ProductionJob:
        from app.domain.errors import EntityNotFoundError

        job = await self._session.get(ProductionJob, job_id)
        if job is None:
            raise EntityNotFoundError("ProductionJob", job_id)

        job.status = status  # type: ignore
        if output_asset_id is not None:
            job.output_asset_id = output_asset_id
        if operations is not None:
            job.operations = operations
        if attempt_count is not None:
            job.attempt_count = attempt_count
        if qa_report is not None:
            job.qa_report = qa_report
        if qa_passed is not None:
            job.qa_passed = qa_passed
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if failure_kind is not None:
            job.failure_kind = failure_kind
        if failure_message is not None:
            job.failure_message = failure_message

        await self._session.flush()
        return job
