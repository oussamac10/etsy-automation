"""Token usage and cost management endpoints.

Allows owners to monitor token consumption, track API provider costs, view execution ledgers,
and adjust daily/monthly budget limits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, UowDep
from app.api.usage_schemas import (
    OperationSpendBreakdown,
    ProviderSpendBreakdown,
    UpdateBudgetLimitsRequest,
    UsageLedgerItem,
    UsageLedgerResponse,
    UsageSummaryResponse,
)
from app.application import owner_settings as settings_use_cases
from app.domain.enums import ProviderName
from app.domain.money import Money
from app.domain.owner_settings import validate_budgets
from app.infrastructure.models import OwnerSettings

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    summary="Get aggregated token usage and cost metrics",
)
async def get_usage_summary(
    uow: UowDep,
    current_user: CurrentUser,
) -> UsageSummaryResponse:
    """Retrieve spend summaries, token counts, budget limits, and provider breakdowns."""
    settings: OwnerSettings | None = await uow.owner_settings.get_for_user(current_user.id)
    if settings is None:
        settings = await settings_use_cases.get_or_create_settings(uow, current_user.id)

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    currency = settings.currency
    metrics = await uow.costs.get_owner_metrics(
        current_user.id,
        today_start=today_start,
        month_start=month_start,
        currency=currency,
    )

    total_spent = Money(metrics["total_spent_minor"], currency).to_decimal()
    today_spent = Money(metrics["today_spent_minor"], currency).to_decimal()
    month_spent = Money(metrics["month_spent_minor"], currency).to_decimal()

    daily_budget = settings.daily_budget.to_decimal()
    monthly_budget = settings.monthly_budget.to_decimal()

    daily_usage_pct = (
        float((today_spent / daily_budget) * 100) if daily_budget > Decimal("0.00") else 0.0
    )
    monthly_usage_pct = (
        float((month_spent / monthly_budget) * 100) if monthly_budget > Decimal("0.00") else 0.0
    )

    # Provider breakdown list
    by_provider_list: list[ProviderSpendBreakdown] = []
    total_spent_minor = metrics["total_spent_minor"]
    for prov_key, p_data in metrics.get("by_provider", {}).items():
        cost_dec = Money(p_data["cost_minor"], currency).to_decimal()
        pct = (
            float((p_data["cost_minor"] / total_spent_minor) * 100)
            if total_spent_minor > 0
            else 0.0
        )
        by_provider_list.append(
            ProviderSpendBreakdown(
                provider=prov_key,
                cost_decimal=cost_dec,
                tokens=p_data["tokens"],
                percentage=round(pct, 1),
            )
        )
    by_provider_list.sort(key=lambda x: x.cost_decimal, reverse=True)

    # Operation breakdown list
    by_op_list: list[OperationSpendBreakdown] = []
    for op_key, op_data in metrics.get("by_operation", {}).items():
        cost_dec = Money(op_data["cost_minor"], currency).to_decimal()
        pct = (
            float((op_data["cost_minor"] / total_spent_minor) * 100)
            if total_spent_minor > 0
            else 0.0
        )
        by_op_list.append(
            OperationSpendBreakdown(
                operation=op_key,
                cost_decimal=cost_dec,
                calls=op_data["calls"],
                percentage=round(pct, 1),
            )
        )
    by_op_list.sort(key=lambda x: x.cost_decimal, reverse=True)

    total_in = metrics["total_input_tokens"]
    total_out = metrics["total_output_tokens"]

    return UsageSummaryResponse(
        currency=currency,
        today_spent=today_spent,
        daily_budget=daily_budget,
        daily_usage_pct=round(daily_usage_pct, 1),
        month_spent=month_spent,
        monthly_budget=monthly_budget,
        monthly_usage_pct=round(monthly_usage_pct, 1),
        total_spent=total_spent,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_tokens=total_in + total_out,
        total_images=metrics["total_images"],
        total_calls=metrics["total_calls"],
        is_paused=settings.is_paused,
        notify_on_budget_warning=settings.notify_on_budget_warning,
        by_provider=by_provider_list,
        by_operation=by_op_list,
        updated_at=now,
    )


@router.get(
    "/ledger",
    response_model=UsageLedgerResponse,
    summary="Get paginated provider usage ledger records",
)
async def get_usage_ledger(
    uow: UowDep,
    current_user: CurrentUser,
    provider: ProviderName | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UsageLedgerResponse:
    """Retrieve detailed provider call records for the authenticated owner."""
    rows = await uow.costs.list_for_owner(
        current_user.id,
        provider=provider,
        limit=limit,
        offset=offset,
    )

    items: list[UsageLedgerItem] = []
    for usage, wf_name in rows:
        est_dec = Money(usage.estimated_cost_minor, usage.currency).to_decimal()
        act_dec = (
            Money(usage.actual_cost_minor, usage.currency).to_decimal()
            if usage.actual_cost_minor is not None
            else None
        )
        eff_dec = Money(usage.effective_cost_minor, usage.currency).to_decimal()

        prov_val = usage.provider.value if hasattr(usage.provider, "value") else str(usage.provider)
        status_val = usage.status.value if hasattr(usage.status, "value") else str(usage.status)

        items.append(
            UsageLedgerItem(
                id=usage.id,
                workflow_id=usage.workflow_id,
                workflow_name=wf_name,
                created_at=usage.created_at,
                provider=prov_val,
                service=usage.service,
                operation=usage.operation,
                input_units=usage.input_units,
                output_units=usage.output_units,
                unit_kind=usage.unit_kind,
                currency=usage.currency,
                estimated_cost=est_dec,
                actual_cost=act_dec,
                effective_cost=eff_dec,
                status=status_val,
            )
        )

    return UsageLedgerResponse(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/budget",
    response_model=UsageSummaryResponse,
    summary="Update budget limits and safety toggles",
)
async def update_budget_limits(
    payload: UpdateBudgetLimitsRequest,
    uow: UowDep,
    current_user: CurrentUser,
) -> UsageSummaryResponse:
    """Update daily budget, monthly budget, alert triggers, or emergency pause."""
    settings: OwnerSettings | None = await uow.owner_settings.get_for_user(current_user.id)
    if settings is None:
        settings = await settings_use_cases.get_or_create_settings(uow, current_user.id)

    daily = payload.daily_budget if payload.daily_budget is not None else settings.daily_budget.to_decimal()
    monthly = (
        payload.monthly_budget
        if payload.monthly_budget is not None
        else settings.monthly_budget.to_decimal()
    )

    validate_budgets(daily, monthly)

    currency = settings.currency
    changes: dict[str, object] = {
        "daily_budget_minor": Money.from_decimal(daily, currency).minor_units,
        "monthly_budget_minor": Money.from_decimal(monthly, currency).minor_units,
    }
    if payload.notify_on_budget_warning is not None:
        changes["notify_on_budget_warning"] = payload.notify_on_budget_warning
    if payload.is_paused is not None:
        changes["is_paused"] = payload.is_paused

    await uow.owner_settings.update(settings, **changes)
    await uow.commit()

    return await get_usage_summary(uow, current_user)
