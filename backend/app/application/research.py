"""Research-run use cases shared by the API and the worker.

The budget gate lives here rather than in the route because the worker enforces
it a second time. The API check is the fast, honest rejection the owner sees;
the worker check is the one that actually protects the wallet, because a queued
message can be delivered long after the API said yes and the ledger may have
moved in between. Two callers, one rule.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Final

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import BudgetExceededError
from app.domain.money import Money
from app.infrastructure.models import OwnerSettings

#: Conservative ceiling for one live research run, in minor units of the owner's
#: currency. ``docs/API_COSTS.md`` puts a run at roughly 10k input plus 5k
#: output tokens on the default synthesis model (about one US cent) plus the
#: search calls. Twenty cents leaves headroom for a run that fans out to more
#: query angles than usual, and an over-estimate only ever rejects too early —
#: an under-estimate lets a run through that the ledger cannot pay for.
RESEARCH_RUN_ESTIMATE_MINOR: Final[int] = 20


def estimate_research_run_cost(*, currency: str, provider_mode: str) -> Money:
    """Cost to expect from one research run before it is dispatched.

    Fake providers make no paid call, so they estimate to zero: a local run must
    never be refused for budget reasons.
    """
    minor = RESEARCH_RUN_ESTIMATE_MINOR if provider_mode == "live" else 0
    return Money(minor, currency)


async def ensure_research_within_budget(
    uow: UnitOfWork,
    *,
    owner_id: uuid.UUID,
    provider_mode: str,
    now: datetime | None = None,
) -> OwnerSettings:
    """Reject a research run that either budget cannot absorb.

    Returns the owner's settings so the caller does not load them twice. Raises
    :class:`BudgetExceededError` before any paid work is dispatched.
    """
    settings = await uow.owner_settings.get_for_user(owner_id)
    if settings is None:
        settings = await uow.owner_settings.create_defaults(owner_id)

    projected = estimate_research_run_cost(
        currency=settings.currency, provider_mode=provider_mode
    )

    # The daily ceiling is checked against the single run rather than the day's
    # spend so far: one run that cannot fit in a whole day's budget is
    # misconfiguration, and reporting it as "daily" tells the owner which limit
    # to raise.
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
