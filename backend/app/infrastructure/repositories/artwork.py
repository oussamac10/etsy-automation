from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import ArtworkJob, Asset


class SqlArtworkJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: ArtworkJob) -> ArtworkJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> ArtworkJob | None:
        return await self._session.get(ArtworkJob, job_id)

    async def get_by_idempotency_key(self, key: str) -> ArtworkJob | None:
        result = await self._session.execute(
            select(ArtworkJob).where(ArtworkJob.idempotency_key == key)
        )
        return result.scalars().first()

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ArtworkJob]:
        result = await self._session.execute(
            select(ArtworkJob)
            .where(ArtworkJob.workflow_id == workflow_id)
            .order_by(ArtworkJob.created_at.desc())
        )
        return result.scalars().all()

    async def update(
        self,
        job_id: uuid.UUID,
        *,
        status: object,
        provider_job_id: str | None = None,
        attempt_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_kind: str | None = None,
        failure_message: str | None = None,
    ) -> ArtworkJob:
        from app.domain.errors import EntityNotFoundError

        job = await self._session.get(ArtworkJob, job_id)
        if job is None:
            raise EntityNotFoundError("ArtworkJob", job_id)

        job.status = status  # type: ignore
        if provider_job_id is not None:
            job.provider_job_id = provider_job_id
        if attempt_count is not None:
            job.attempt_count = attempt_count
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


class SqlAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, asset: Asset) -> Asset:
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def get(self, asset_id: uuid.UUID) -> Asset | None:
        return await self._session.get(Asset, asset_id)

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[Asset]:
        result = await self._session.execute(
            select(Asset).where(Asset.workflow_id == workflow_id).order_by(Asset.created_at.desc())
        )
        return result.scalars().all()

    async def list_for_job(self, job_id: uuid.UUID) -> Sequence[Asset]:
        result = await self._session.execute(
            select(Asset).where(Asset.artwork_job_id == job_id).order_by(Asset.created_at)
        )
        return result.scalars().all()

    async def get_by_checksum_sha256(self, workflow_id: uuid.UUID, sha256: str) -> Asset | None:
        result = await self._session.execute(
            select(Asset).where(
                Asset.workflow_id == workflow_id,
                Asset.checksum_sha256 == sha256,
            )
        )
        return result.scalars().first()

    async def delete(self, asset: Asset) -> None:
        await self._session.delete(asset)
        await self._session.flush()
