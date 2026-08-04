from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.workflow import JobStatus
from app.infrastructure.models.research import ResearchRun, ResearchEvidence, KeywordCluster


class SqlResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_run(self, workflow_id: uuid.UUID) -> ResearchRun:
        # Get next run number
        result = await self._session.execute(
            select(func.coalesce(func.max(ResearchRun.run_number), 0))
            .where(ResearchRun.workflow_id == workflow_id)
        )
        highest = result.scalar_one()
        run_number = highest + 1

        run = ResearchRun(
            workflow_id=workflow_id,
            run_number=run_number,
            status=JobStatus.QUEUED,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> ResearchRun | None:
        return await self._session.get(ResearchRun, run_id)

    async def get_latest_run(self, workflow_id: uuid.UUID) -> ResearchRun | None:
        result = await self._session.execute(
            select(ResearchRun)
            .where(ResearchRun.workflow_id == workflow_id)
            .order_by(ResearchRun.run_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_runs_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ResearchRun]:
        result = await self._session.execute(
            select(ResearchRun)
            .where(ResearchRun.workflow_id == workflow_id)
            .order_by(ResearchRun.run_number.desc())
        )
        return result.scalars().all()

    async def update_run(
        self,
        run_id: uuid.UUID,
        *,
        status: object,
        confidence: object | None = None,
        proposed_test: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_reason: str | None = None,
        query_angles: list[str] | None = None,
    ) -> ResearchRun:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"ResearchRun {run_id} not found.")

        run.status = status  # type: ignore[assignment]
        if confidence is not None:
            run.confidence = confidence  # type: ignore[assignment]
        if proposed_test is not None:
            run.proposed_test = proposed_test
        if started_at is not None:
            run.started_at = started_at
        if completed_at is not None:
            run.completed_at = completed_at
        if failure_reason is not None:
            run.failure_reason = failure_reason
        if query_angles is not None:
            run.query_angles = query_angles

        await self._session.flush()
        return run

    async def add_evidence(self, evidence: ResearchEvidence) -> ResearchEvidence:
        self._session.add(evidence)
        await self._session.flush()
        return evidence

    async def get_evidence_for_run(self, run_id: uuid.UUID) -> Sequence[ResearchEvidence]:
        result = await self._session.execute(
            select(ResearchEvidence)
            .where(ResearchEvidence.run_id == run_id)
            .order_by(ResearchEvidence.created_at)
        )
        return result.scalars().all()

    async def add_keyword_cluster(self, cluster: KeywordCluster) -> KeywordCluster:
        self._session.add(cluster)
        await self._session.flush()
        return cluster

    async def get_keyword_clusters_for_run(self, run_id: uuid.UUID) -> Sequence[KeywordCluster]:
        result = await self._session.execute(
            select(KeywordCluster)
            .where(KeywordCluster.run_id == run_id)
            .order_by(KeywordCluster.relevance_rank.desc())
        )
        return result.scalars().all()
