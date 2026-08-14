"""The budget gate in front of every research run.

These run against a real database because the monthly check reads the cost
ledger, and the whole point of the gate is that it sees what was actually
spent rather than what a stub says was spent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.research import (
    RESEARCH_RUN_ESTIMATE_MINOR,
    ensure_research_within_budget,
    estimate_research_run_cost,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import IdeaMode, ProviderName
from app.domain.errors import BudgetExceededError
from app.domain.money import Money
from app.infrastructure.models import User

pytestmark = pytest.mark.integration


async def _workflow_for(uow: UnitOfWork, owner_id: uuid.UUID) -> uuid.UUID:
    """A workflow to hang ledger entries on; usage is recorded per workflow."""
    from app.application.workflows import CreateWorkflowCommand, create_workflow

    workflow = await create_workflow(
        uow,
        CreateWorkflowCommand(
            owner_id=owner_id,
            idea_mode=IdeaMode.MARKET_LED,
            name="Budget fixture",
            target_country="US",
            output_language="en",
        ),
    )
    return workflow.id


class TestEstimate:
    def test_fake_mode_costs_nothing(self) -> None:
        # A local run makes no paid call, so it must never be refused.
        assert estimate_research_run_cost(currency="USD", provider_mode="fake") == Money(
            0, "USD"
        )

    def test_live_mode_uses_the_documented_ceiling(self) -> None:
        assert estimate_research_run_cost(currency="USD", provider_mode="live") == Money(
            RESEARCH_RUN_ESTIMATE_MINOR, "USD"
        )

    def test_estimate_follows_the_owners_currency(self) -> None:
        assert estimate_research_run_cost(currency="EUR", provider_mode="live").currency == "EUR"


class TestEnsureWithinBudget:
    async def test_fake_mode_passes_even_with_a_zero_budget(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        settings = await uow.owner_settings.create_defaults(owner.id)
        settings.daily_budget_minor = 0
        settings.monthly_budget_minor = 0
        await uow.commit()

        await ensure_research_within_budget(
            uow, owner_id=owner.id, provider_mode="fake"
        )

    async def test_creates_default_settings_when_the_owner_has_none(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        assert await uow.owner_settings.get_for_user(owner.id) is None

        settings = await ensure_research_within_budget(
            uow, owner_id=owner.id, provider_mode="live"
        )

        assert settings.user_id == owner.id

    async def test_rejects_a_run_larger_than_the_daily_budget(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        settings = await uow.owner_settings.create_defaults(owner.id)
        # One run cannot fit in a whole day: misconfiguration, reported as daily
        # so the owner knows which limit to raise.
        settings.daily_budget_minor = RESEARCH_RUN_ESTIMATE_MINOR - 1
        await uow.commit()

        with pytest.raises(BudgetExceededError) as caught:
            await ensure_research_within_budget(
                uow, owner_id=owner.id, provider_mode="live"
            )

        assert caught.value.scope == "daily"

    async def test_rejects_when_the_month_is_already_spent(
        self, uow: UnitOfWork, owner: User, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        settings = await uow.owner_settings.create_defaults(owner.id)
        settings.daily_budget_minor = 500
        settings.monthly_budget_minor = 500
        workflow_id = await _workflow_for(uow, owner.id)
        await uow.costs.record_estimate(
            workflow_id=workflow_id,
            provider=ProviderName.OPENAI,
            service="text",
            operation="synthesis",
            estimated=Money(490, "USD"),
        )
        await uow.commit()

        # 490 already spent plus this run's 20 breaches the 500 ceiling.
        with pytest.raises(BudgetExceededError) as caught:
            await ensure_research_within_budget(
                uow, owner_id=owner.id, provider_mode="live"
            )

        assert caught.value.scope == "monthly"

    async def test_ignores_spend_from_a_previous_month(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        settings = await uow.owner_settings.create_defaults(owner.id)
        settings.daily_budget_minor = 500
        settings.monthly_budget_minor = 500
        workflow_id = await _workflow_for(uow, owner.id)
        usage = await uow.costs.record_estimate(
            workflow_id=workflow_id,
            provider=ProviderName.OPENAI,
            service="text",
            operation="synthesis",
            estimated=Money(490, "USD"),
        )
        # Backdate the ledger entry into the previous month. A monthly ceiling
        # that never resets would be a bug the owner only notices on the 1st.
        usage.created_at = datetime(2020, 1, 15, tzinfo=UTC)
        await uow.commit()

        await ensure_research_within_budget(
            uow, owner_id=owner.id, provider_mode="live"
        )

    async def test_ignores_another_owners_spend(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        stranger = await uow.users.add(
            email="stranger@example.invalid", display_name="Stranger"
        )
        settings = await uow.owner_settings.create_defaults(owner.id)
        settings.daily_budget_minor = 500
        settings.monthly_budget_minor = 500
        stranger_workflow = await _workflow_for(uow, stranger.id)
        await uow.costs.record_estimate(
            workflow_id=stranger_workflow,
            provider=ProviderName.OPENAI,
            service="text",
            operation="synthesis",
            estimated=Money(490, "USD"),
        )
        await uow.commit()

        await ensure_research_within_budget(
            uow, owner_id=owner.id, provider_mode="live"
        )
