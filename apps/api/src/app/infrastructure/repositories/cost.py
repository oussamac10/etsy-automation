"""Cost ledger repository.

Every aggregate is computed in SQL over integer minor units and returned as
:class:`~app.domain.money.Money`. No float ever touches an amount.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CostStatus, ProviderName
from app.domain.errors import EntityNotFoundError
from app.domain.money import Money
from app.infrastructure.models import ProviderUsage


def _effective_cost_sql() -> object:
    """SQL mirror of ``ProviderUsage.effective_cost_minor``.

    A voided reservation counts as nothing; otherwise the reconciled amount wins
    and the estimate stands in until it arrives. Kept next to the Python property
    so the two definitions of "what has this cost" cannot drift apart.
    """
    return case(
        (ProviderUsage.status == CostStatus.VOIDED, 0),
        (
            ProviderUsage.actual_cost_minor.isnot(None),
            ProviderUsage.actual_cost_minor,
        ),
        else_=ProviderUsage.estimated_cost_minor,
    )


class SqlCostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_estimate(
        self,
        *,
        workflow_id: uuid.UUID,
        provider: ProviderName,
        service: str,
        operation: str,
        estimated: Money,
        input_units: int = 0,
        output_units: int = 0,
        unit_kind: str = "units",
        idempotency_key: str | None = None,
        price_reference: dict[str, object] | None = None,
        artwork_job_id: uuid.UUID | None = None,
    ) -> ProviderUsage:
        usage = ProviderUsage(
            workflow_id=workflow_id,
            artwork_job_id=artwork_job_id,
            provider=provider,
            service=service,
            operation=operation,
            input_units=input_units,
            output_units=output_units,
            unit_kind=unit_kind,
            currency=estimated.currency,
            estimated_cost_minor=estimated.minor_units,
            actual_cost_minor=None,
            status=CostStatus.ESTIMATED,
            price_reference=price_reference or {},
            idempotency_key=idempotency_key,
        )
        self._session.add(usage)
        await self._session.flush()
        return usage

    async def find_by_idempotency_key(self, key: str) -> ProviderUsage | None:
        """Used to make cost recording idempotent under duplicate delivery."""
        result = await self._session.execute(
            select(ProviderUsage).where(ProviderUsage.idempotency_key == key)
        )
        return result.scalars().first()

    async def reconcile(
        self,
        usage_id: uuid.UUID,
        *,
        actual: Money,
        input_units: int | None = None,
        output_units: int | None = None,
    ) -> ProviderUsage:
        usage = await self._session.get(ProviderUsage, usage_id)
        if usage is None:
            raise EntityNotFoundError("ProviderUsage", usage_id)
        if actual.currency != usage.currency:
            raise ValueError(f"Cannot reconcile a {usage.currency} entry with {actual.currency}.")

        usage.actual_cost_minor = actual.minor_units
        usage.status = CostStatus.RECONCILED
        if input_units is not None:
            usage.input_units = input_units
        if output_units is not None:
            usage.output_units = output_units
        await self._session.flush()
        return usage

    async def void(self, usage_id: uuid.UUID) -> ProviderUsage:
        """Release a reservation for an operation that never ran."""
        usage = await self._session.get(ProviderUsage, usage_id)
        if usage is None:
            raise EntityNotFoundError("ProviderUsage", usage_id)
        usage.status = CostStatus.VOIDED
        usage.actual_cost_minor = 0
        await self._session.flush()
        return usage

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ProviderUsage]:
        result = await self._session.execute(
            select(ProviderUsage)
            .where(ProviderUsage.workflow_id == workflow_id)
            .order_by(ProviderUsage.created_at)
        )
        return result.scalars().all()

    async def _sum(self, stmt: Select[Any], currency: str) -> Money:
        result = await self._session.execute(stmt)
        total = result.scalar_one_or_none()
        return Money(int(total or 0), currency)

    async def total_for_workflow(self, workflow_id: uuid.UUID, *, currency: str = "USD") -> Money:
        """Per-listing total."""
        stmt = select(func.sum(_effective_cost_sql())).where(
            ProviderUsage.workflow_id == workflow_id,
            ProviderUsage.currency == currency,
        )
        return await self._sum(stmt, currency)

    async def total_for_provider(
        self,
        provider: ProviderName,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        currency: str = "USD",
    ) -> Money:
        """Per-provider total, optionally within a window."""
        stmt = select(func.sum(_effective_cost_sql())).where(
            ProviderUsage.provider == provider,
            ProviderUsage.currency == currency,
        )
        if since is not None:
            stmt = stmt.where(ProviderUsage.created_at >= since)
        if until is not None:
            stmt = stmt.where(ProviderUsage.created_at < until)
        return await self._sum(stmt, currency)

    async def total_by_operation(
        self, workflow_id: uuid.UUID, *, currency: str = "USD"
    ) -> dict[str, Money]:
        """Per-operation totals for one workflow."""
        result = await self._session.execute(
            select(ProviderUsage.operation, func.sum(_effective_cost_sql()))
            .where(
                ProviderUsage.workflow_id == workflow_id,
                ProviderUsage.currency == currency,
            )
            .group_by(ProviderUsage.operation)
        )
        return {operation: Money(int(amount or 0), currency) for operation, amount in result.all()}

    async def total_in_period(
        self,
        *,
        since: datetime,
        until: datetime,
        currency: str = "USD",
        status: CostStatus | None = None,
    ) -> Money:
        """Monthly (or any window) total, for budget comparison."""
        stmt = select(func.sum(_effective_cost_sql())).where(
            ProviderUsage.created_at >= since,
            ProviderUsage.created_at < until,
            ProviderUsage.currency == currency,
        )
        if status is not None:
            stmt = stmt.where(ProviderUsage.status == status)
        return await self._sum(stmt, currency)

    async def would_exceed_budget(self, *, current: Money, projected: Money, limit: Money) -> bool:
        """Compare-before-dispatch helper. Pure integer arithmetic."""
        return (current + projected) > limit
