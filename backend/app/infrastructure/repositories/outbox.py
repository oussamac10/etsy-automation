from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.outbox import OutboxMessage


class SqlOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event_type: str, payload: dict[str, object]) -> OutboxMessage:
        message = OutboxMessage(event_type=event_type, payload=payload, processed=False)
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_unprocessed(self, *, limit: int = 100) -> Sequence[OutboxMessage]:
        """Claim a batch of undispatched messages for this publisher.

        ``FOR UPDATE SKIP LOCKED`` is what makes more than one API replica safe:
        each publisher takes rows nobody else holds instead of every replica
        dispatching the same backlog.
        """
        result = await self._session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed.is_(False))
            .order_by(OutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return result.scalars().all()

    async def mark_processed(self, message_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(OutboxMessage).where(OutboxMessage.id == message_id)
        )
        message = result.scalar_one_or_none()
        if message:
            message.processed = True
            await self._session.flush()
