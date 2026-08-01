"""Audit repository. Append-only.

Metadata passes through the same redaction the structured logger uses, so an
audit event can never become the place a secret leaks. Cost, approval and
provenance records are never deleted by application flows, so this class offers
no delete.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditAction
from app.infrastructure.logging import redact_secrets
from app.infrastructure.models import AuditEvent


def _redact(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop secret-shaped keys at any depth before the value is persisted."""
    if payload is None:
        return None
    return dict(redact_secrets(None, "audit", dict(payload)))


class SqlAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        summary: str,
        workflow_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        approval_id: uuid.UUID | None = None,
        actor: str = "system",
        correlation_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workflow_id=workflow_id,
            approval_id=approval_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            correlation_id=correlation_id,
            before=_redact(before),
            after=_redact(after),
            event_metadata=_redact(metadata) or {},
            summary=summary,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def for_workflow(
        self, workflow_id: uuid.UUID, *, limit: int = 200
    ) -> Sequence[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(AuditEvent.workflow_id == workflow_id)
            .order_by(AuditEvent.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def for_entity(self, entity_type: str, entity_id: uuid.UUID) -> Sequence[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.created_at)
        )
        return result.scalars().all()
