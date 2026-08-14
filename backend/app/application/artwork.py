from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import BudgetExceededError
from app.domain.money import Money
from app.infrastructure.models import OwnerSettings


def estimate_artwork_cost(
    *,
    provider: str | None = None,
    model: str | None = None,
    candidate_count: int = 1,
    currency: str = "USD",
    provider_mode: str = "fake",
) -> Money:
    """Cost to expect from one artwork generation run before it is dispatched.

    Fake providers make no paid call, so they estimate to zero: a local run must
    never be refused for budget reasons.
    """
    if provider_mode != "live":
        return Money.zero(currency)

    p_lower = (provider or "recraft").lower()
    m_lower = (model or "").lower()

    if p_lower == "recraft":
        if "pro" in m_lower:
            unit_price = Decimal("0.21")
        elif "vector" in m_lower:
            unit_price = Decimal("0.08")
        else:
            unit_price = Decimal("0.035")
    elif p_lower == "gemini":
        if "pro" in m_lower:
            unit_price = Decimal("0.15")
        else:
            unit_price = Decimal("0.03")
    else:
        unit_price = Decimal("0.035")

    total = unit_price * candidate_count
    return Money.from_decimal(total, currency)


async def ensure_artwork_within_budget(
    uow: UnitOfWork,
    *,
    owner_id: uuid.UUID,
    provider: str | None = None,
    model: str | None = None,
    candidate_count: int = 1,
    provider_mode: str = "fake",
    now: datetime | None = None,
) -> OwnerSettings:
    """Reject an artwork run that either budget cannot absorb.

    Returns the owner's settings so the caller does not load them twice. Raises
    :class:`BudgetExceededError` before any paid work is dispatched.
    """
    settings = await uow.owner_settings.get_for_user(owner_id)
    if settings is None:
        settings = await uow.owner_settings.create_defaults(owner_id)

    projected = estimate_artwork_cost(
        provider=provider,
        model=model,
        candidate_count=candidate_count,
        currency=settings.currency,
        provider_mode=provider_mode,
    )

    if projected > settings.daily_budget:
        raise BudgetExceededError(
            scope="daily",
            limit_minor=settings.daily_budget.minor_units,
            projected_minor=projected.minor_units,
            currency=settings.currency,
        )

    moment = now or datetime.now(UTC)
    month_start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
    spent = await uow.costs.total_for_owner_in_period(
        owner_id=owner_id,
        since=month_start,
        until=moment,
        currency=settings.currency,
    )
    if (spent + projected) > settings.monthly_budget:
        raise BudgetExceededError(
            scope="monthly",
            limit_minor=settings.monthly_budget.minor_units,
            projected_minor=(spent + projected).minor_units,
            currency=settings.currency,
        )

    return settings
