"""Pydantic schemas for Token Usage and Cost Management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProviderSpendBreakdown(BaseModel):
    provider: str
    cost_decimal: Decimal
    tokens: int
    percentage: float = 0.0


class OperationSpendBreakdown(BaseModel):
    operation: str
    cost_decimal: Decimal
    calls: int
    percentage: float = 0.0


class UsageSummaryResponse(BaseModel):
    currency: str = "USD"
    # Spend & Budget
    today_spent: Decimal
    daily_budget: Decimal
    daily_usage_pct: float
    month_spent: Decimal
    monthly_budget: Decimal
    monthly_usage_pct: float
    total_spent: Decimal
    # Token & Units Counters
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_images: int
    total_calls: int
    # Controls
    is_paused: bool
    notify_on_budget_warning: bool
    # Breakdowns
    by_provider: list[ProviderSpendBreakdown]
    by_operation: list[OperationSpendBreakdown]
    updated_at: datetime


class UsageLedgerItem(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str
    created_at: datetime
    provider: str
    service: str
    operation: str
    input_units: int
    output_units: int
    unit_kind: str
    currency: str
    estimated_cost: Decimal
    actual_cost: Decimal | None
    effective_cost: Decimal
    status: str


class UsageLedgerResponse(BaseModel):
    items: list[UsageLedgerItem]
    total: int
    limit: int
    offset: int


class UpdateBudgetLimitsRequest(BaseModel):
    daily_budget: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("1000.00"))
    monthly_budget: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("10000.00"))
    notify_on_budget_warning: bool | None = None
    is_paused: bool | None = None
