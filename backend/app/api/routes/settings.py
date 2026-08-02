"""Owner settings and provider credentials.

Every route here is owner-scoped through :data:`CurrentUser`. None of them
accepts an owner ID, so there is no cross-owner request to reject — the shape of
the API makes it unrepresentable.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, status

from app.api.auth_schemas import (
    CredentialListResponse,
    CredentialResponse,
    SettingsResponse,
    StoreCredentialRequest,
    TelegramConnectionResponse,
    TelegramPairingCodeResponse,
    UpdateSettingsRequest,
)
from app.api.dependencies import CipherDep, CurrentUser, UowDep
from app.application import owner_settings as use_cases
from app.application.owner_settings import CredentialSummary
from app.domain.enums import ProviderName
from app.domain.money import Money
from app.domain.owner_settings import validate_budgets
from app.infrastructure.models import OwnerSettings

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_response(settings: OwnerSettings) -> SettingsResponse:
    """Minor units become a two-place decimal at the boundary, never a float."""
    return SettingsResponse(
        target_marketplace=settings.target_marketplace,
        target_country=settings.target_country,
        currency=settings.currency,
        default_language=settings.default_language,
        default_idea_mode=settings.default_idea_mode,
        default_target_buyer=settings.default_target_buyer,
        default_product_uses=list(settings.default_product_uses),
        style_preferences=list(settings.style_preferences),
        style_notes=settings.style_notes,
        avoid_terms=list(settings.avoid_terms),
        default_quality_tier=settings.default_quality_tier,
        min_output_pixels=settings.min_output_pixels,
        require_transparent_background=settings.require_transparent_background,
        daily_budget=settings.daily_budget.to_decimal(),
        monthly_budget=settings.monthly_budget.to_decimal(),
        weekly_research_enabled=settings.weekly_research_enabled,
        weekly_research_weekday=settings.weekly_research_weekday,
        weekly_research_hour_utc=settings.weekly_research_hour_utc,
        notify_on_failure=settings.notify_on_failure,
        notify_on_budget_warning=settings.notify_on_budget_warning,
        notify_on_approval_needed=settings.notify_on_approval_needed,
        updated_at=settings.updated_at,
    )


def _credential_response(summary: CredentialSummary) -> CredentialResponse:
    return CredentialResponse(
        provider=summary.provider,
        configured=summary.configured,
        masked_value=summary.masked_value,
        label=summary.label,
        key_version=summary.key_version,
        updated_at=summary.updated_at,
    )


def _build_changes(payload: UpdateSettingsRequest, current: OwnerSettings) -> dict[str, Any]:
    """Turn a partial request into column assignments.

    ``exclude_unset`` is what makes the update genuinely partial: a field the
    client did not send is absent here, so ``None`` still means "set this to
    null" for the fields that are nullable.
    """
    changes: dict[str, Any] = payload.model_dump(exclude_unset=True)

    # Budgets arrive as decimals and are stored as minor units of the currency
    # *after* this update, so a currency change and a budget change in one
    # request are converted consistently.
    currency = str(changes.get("currency", current.currency))
    daily = changes.pop("daily_budget", None)
    monthly = changes.pop("monthly_budget", None)

    resolved_daily: Decimal = daily if daily is not None else current.daily_budget.to_decimal()
    resolved_monthly: Decimal = (
        monthly if monthly is not None else current.monthly_budget.to_decimal()
    )
    # Raises BudgetRelationError -> 422. Also a CHECK constraint, so a future
    # caller that bypasses this schema still cannot write the bad combination.
    validate_budgets(resolved_daily, resolved_monthly)

    if daily is not None or currency != current.currency:
        changes["daily_budget_minor"] = Money.from_decimal(resolved_daily, currency).minor_units
    if monthly is not None or currency != current.currency:
        changes["monthly_budget_minor"] = Money.from_decimal(resolved_monthly, currency).minor_units
    return changes


@router.get("", response_model=SettingsResponse, summary="The owner's settings")
async def get_settings(user: CurrentUser, uow: UowDep) -> SettingsResponse:
    """Defaults are materialised on first read, so this never 404s."""
    settings = await use_cases.get_or_create_settings(uow, user.id)
    return _to_response(settings)


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update some settings",
    responses={422: {"description": "A value or combination is not allowed"}},
)
async def update_settings(
    payload: UpdateSettingsRequest, user: CurrentUser, uow: UowDep
) -> SettingsResponse:
    current = await use_cases.get_or_create_settings(uow, user.id)
    settings = await use_cases.update_settings(uow, user.id, _build_changes(payload, current))
    return _to_response(settings)


@router.get(
    "/credentials",
    response_model=CredentialListResponse,
    summary="Which provider credentials are configured",
)
async def list_credentials(user: CurrentUser, uow: UowDep) -> CredentialListResponse:
    """Every supported provider, with a mask instead of a value."""
    summaries = await use_cases.list_credentials(uow, user.id)
    return CredentialListResponse(items=[_credential_response(item) for item in summaries])


@router.put(
    "/credentials/{provider}",
    response_model=CredentialResponse,
    summary="Store or replace a provider credential",
    responses={
        404: {"description": "Unknown provider"},
        503: {"description": "Credential encryption is not configured"},
    },
)
async def store_credential(
    provider: ProviderName,
    payload: StoreCredentialRequest,
    user: CurrentUser,
    uow: UowDep,
    cipher: CipherDep,
) -> CredentialResponse:
    """The secret is encrypted before it reaches the database and never echoed."""
    summary = await use_cases.store_credential(
        uow,
        user.id,
        provider=provider,
        secret=payload.secret.get_secret_value(),
        label=payload.label,
        cipher=cipher,
    )
    return _credential_response(summary)


@router.delete(
    "/credentials/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stored provider credential",
    responses={404: {"description": "No credential stored for that provider"}},
)
async def delete_credential(provider: ProviderName, user: CurrentUser, uow: UowDep) -> None:
    await use_cases.delete_credential(uow, user.id, provider=provider)


@router.get(
    "/telegram",
    response_model=TelegramConnectionResponse,
    summary="Get current owner's Telegram connection status",
)
async def get_telegram_status(user: CurrentUser, uow: UowDep) -> TelegramConnectionResponse:
    conn = await uow.telegram_connections.get_by_user_id(user.id)
    if conn is None or not conn.is_paired:
        return TelegramConnectionResponse(
            paired=False,
            telegram_username=None,
            pairing_code_expires_at=conn.pairing_code_expires_at if conn else None,
        )
    return TelegramConnectionResponse(
        paired=True,
        telegram_username=conn.telegram_username,
        pairing_code_expires_at=None,
    )


@router.post(
    "/telegram/pairing-code",
    response_model=TelegramPairingCodeResponse,
    summary="Generate a short-lived Telegram pairing code",
)
async def generate_telegram_pairing_code(
    user: CurrentUser, uow: UowDep
) -> TelegramPairingCodeResponse:
    from app.application.telegram import generate_pairing_code

    code, expires_at = await generate_pairing_code(uow, user.id)
    return TelegramPairingCodeResponse(pairing_code=code, expires_at=expires_at)


@router.delete(
    "/telegram",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect the Telegram connection",
)
async def disconnect_telegram_bot(user: CurrentUser, uow: UowDep) -> None:
    from app.application.telegram import disconnect_telegram

    await disconnect_telegram(uow, user.id)
