from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.usage_schemas import (
    OperationSpendBreakdown,
    ProviderSpendBreakdown,
    UpdateBudgetLimitsRequest,
    UsageLedgerItem,
    UsageLedgerResponse,
    UsageSummaryResponse,
)
from app.domain.enums import CostStatus, ProviderName
from app.domain.money import Money
from app.infrastructure.models import OwnerSettings, ProviderUsage, User
from app.main import create_app
from app.settings import Settings


def test_usage_endpoints_registered_in_openapi(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    document = client.get("/api/openapi.json").json()
    assert "/api/v1/usage/summary" in document["paths"]
    assert "/api/v1/usage/ledger" in document["paths"]
    assert "/api/v1/usage/budget" in document["paths"]


def test_usage_summary_schema_serialization() -> None:
    now = datetime.now(UTC)
    summary = UsageSummaryResponse(
        currency="USD",
        today_spent=Decimal("0.45"),
        daily_budget=Decimal("2.00"),
        daily_usage_pct=22.5,
        month_spent=Decimal("12.80"),
        monthly_budget=Decimal("30.00"),
        monthly_usage_pct=42.7,
        total_spent=Decimal("45.60"),
        total_input_tokens=150000,
        total_output_tokens=35000,
        total_tokens=185000,
        total_images=24,
        total_calls=58,
        is_paused=False,
        notify_on_budget_warning=True,
        by_provider=[
            ProviderSpendBreakdown(
                provider="gemini",
                cost_decimal=Decimal("0.25"),
                tokens=120000,
                percentage=55.6,
            ),
            ProviderSpendBreakdown(
                provider="recraft",
                cost_decimal=Decimal("0.20"),
                tokens=0,
                percentage=44.4,
            ),
        ],
        by_operation=[
            OperationSpendBreakdown(
                operation="text_synthesis",
                cost_decimal=Decimal("0.25"),
                calls=30,
                percentage=55.6,
            ),
            OperationSpendBreakdown(
                operation="image_generation",
                cost_decimal=Decimal("0.20"),
                calls=10,
                percentage=44.4,
            ),
        ],
        updated_at=now,
    )

    data = summary.model_dump(mode="json")
    assert data["currency"] == "USD"
    assert data["total_tokens"] == 185000
    assert len(data["by_provider"]) == 2
    assert data["daily_usage_pct"] == 22.5


def test_usage_ledger_item_serialization() -> None:
    item = UsageLedgerItem(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        workflow_name="Cozy Autumn Cat",
        created_at=datetime.now(UTC),
        provider="gemini",
        service="gemini-2.5-flash",
        operation="text_synthesis",
        input_units=1200,
        output_units=450,
        unit_kind="tokens",
        currency="USD",
        estimated_cost=Decimal("0.0012"),
        actual_cost=Decimal("0.0011"),
        effective_cost=Decimal("0.0011"),
        status="reconciled",
    )
    res = UsageLedgerResponse(items=[item], total=1, limit=50, offset=0)
    data = res.model_dump(mode="json")
    assert len(data["items"]) == 1
    assert data["items"][0]["workflow_name"] == "Cozy Autumn Cat"
    assert data["items"][0]["status"] == "reconciled"


def test_update_budget_limits_request_validation() -> None:
    req = UpdateBudgetLimitsRequest(
        daily_budget=Decimal("5.00"),
        monthly_budget=Decimal("50.00"),
        is_paused=True,
    )
    assert req.daily_budget == Decimal("5.00")
    assert req.monthly_budget == Decimal("50.00")
    assert req.is_paused is True
