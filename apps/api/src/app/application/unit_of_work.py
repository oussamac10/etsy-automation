"""Unit of work.

One transaction per use case. The repositories are constructed around a single
session so an entity, its transition and its audit event either all land or none
do — a state change without its audit row would be worse than no change at all.

No provider call ever happens inside this boundary: a database transaction must
never be held open across a network request (root CLAUDE.md).
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories import (
    SqlApprovalRepository,
    SqlAuditRepository,
    SqlConceptRepository,
    SqlCostRepository,
    SqlIdeaRepository,
    SqlUserRepository,
    SqlWorkflowRepository,
)


class UnitOfWork:
    """Async context manager holding one session and its repositories."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        session = self._session

        self.users = SqlUserRepository(session)
        self.workflows = SqlWorkflowRepository(session)
        self.ideas = SqlIdeaRepository(session)
        self.concepts = SqlConceptRepository(session)
        self.approvals = SqlApprovalRepository(session)
        self.costs = SqlCostRepository(session)
        self.audit = SqlAuditRepository(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            # Any exception escaping the block rolls the whole unit back,
            # including the audit rows written before the failure.
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:  # pragma: no cover - programming error
            raise RuntimeError("UnitOfWork used outside its context manager")
        return self._session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
