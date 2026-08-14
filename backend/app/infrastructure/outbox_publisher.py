from __future__ import annotations

import asyncio

import dramatiq
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.infrastructure.logging import get_logger

logger = get_logger("outbox_publisher")


class OutboxPublisher:
    """Transactional outbox publisher running as a background asyncio task.

    Polls for unprocessed outbox messages and reliably enqueues them into Dramatiq.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._publish_messages())
        logger.info("outbox_publisher_started")

    def stop(self) -> None:
        if self._task:
            self._stop_event.set()
            self._task.cancel()
            logger.info("outbox_publisher_stopped")

    async def _publish_messages(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with UnitOfWork(self._session_factory) as uow:
                    messages = await uow.outbox.get_unprocessed(limit=50)
                    for msg in messages:
                        try:
                            # ``event_type`` is the target actor's name. The
                            # outbox row's own ID becomes the broker message ID,
                            # so a redelivery after a crash between enqueue and
                            # commit carries the same ID rather than looking
                            # like a second job.
                            dramatiq_msg: dramatiq.Message[None] = dramatiq.Message(
                                queue_name="default",
                                actor_name=msg.event_type,
                                args=(),
                                kwargs=msg.payload,
                                options={},
                                message_id=str(msg.id),
                            )
                            dramatiq.get_broker().enqueue(dramatiq_msg)
                            await uow.outbox.mark_processed(msg.id)
                            logger.info(
                                "outbox_message_dispatched",
                                message_id=str(msg.id),
                                event_type=msg.event_type,
                            )
                        except Exception as e:
                            logger.exception(
                                "outbox_message_dispatch_failed",
                                message_id=str(msg.id),
                                error=str(e),
                            )
                    await uow.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("outbox_publisher_loop_failed", error=str(e))

            # Sleep poll interval or until cancelled
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
