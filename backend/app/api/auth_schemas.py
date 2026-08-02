"""Request and response models for authentication and settings.

Two rules run through this file:

1. No request model has an ``owner_id``. Ownership comes from the session.
2. No response model has a field that could hold a secret. The credential
   response carries a mask, not a value, because a field that *can* hold a
   secret eventually will.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.domain.enums import IdeaMode, ProviderName, QualityTier
from app.domain.owner_settings import (
    MAX_AVOID_TERMS,
    MAX_DAILY_BUDGET,
    MAX_MONTHLY_BUDGET,
    MAX_NOTES_LENGTH,
    MAX_PRODUCT_USES,
    MAX_STYLE_PREFERENCE_LENGTH,
    MAX_STYLE_PREFERENCES,
    MIN_BUDGET,
    SUPPORTED_CURRENCIES,
    SUPPORTED_MARKETPLACES,
)

#: Two decimal places, matching the minor-unit storage. `Decimal`, never float.
BudgetAmount = Annotated[Decimal, Field(ge=MIN_BUDGET, decimal_places=2)]
CountryCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]
LanguageCode = Annotated[str, Field(min_length=2, max_length=10, pattern=r"^[A-Za-z-]{2,10}$")]
StylePreference = Annotated[str, Field(min_length=1, max_length=MAX_STYLE_PREFERENCE_LENGTH)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Shape-checked, not RFC-validated. This is a lookup key against a table
    #: with exactly one row; a stricter parser would add a dependency and
    #: reject nothing that matters.
    email: Annotated[str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")]
    #: ``SecretStr`` so an accidental ``repr`` of the request model in a log or
    #: a traceback prints ``**********`` instead of the password.
    password: Annotated[SecretStr, Field(min_length=1, max_length=1024)]


class CurrentUserResponse(BaseModel):
    """Who is signed in. Deliberately holds no hash, session or token."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool


class LoginResponse(BaseModel):
    """The session token is not here — it is in an ``HttpOnly`` cookie."""

    user: CurrentUserResponse
    expires_at: datetime


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_marketplace: str
    target_country: str
    currency: str
    default_language: str

    default_idea_mode: IdeaMode
    default_target_buyer: str | None
    default_product_uses: list[str]

    style_preferences: list[str]
    style_notes: str | None
    avoid_terms: list[str]

    default_quality_tier: QualityTier
    min_output_pixels: int
    require_transparent_background: bool

    daily_budget: Decimal
    monthly_budget: Decimal

    weekly_research_enabled: bool
    weekly_research_weekday: int
    weekly_research_hour_utc: int
    notify_on_failure: bool
    notify_on_budget_warning: bool
    notify_on_approval_needed: bool

    updated_at: datetime


class UpdateSettingsRequest(BaseModel):
    """Partial update: every field is optional and unset fields are untouched.

    ``extra="forbid"`` means a typo in a field name is a 422 rather than a
    silently ignored change the owner believes they made.
    """

    model_config = ConfigDict(extra="forbid")

    target_marketplace: Annotated[str, Field(max_length=50)] | None = None
    target_country: CountryCode | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    default_language: LanguageCode | None = None

    default_idea_mode: IdeaMode | None = None
    default_target_buyer: Annotated[str | None, Field(max_length=MAX_NOTES_LENGTH)] = None
    default_product_uses: (
        Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=MAX_PRODUCT_USES)]
        | None
    ) = None

    style_preferences: (
        Annotated[list[StylePreference], Field(max_length=MAX_STYLE_PREFERENCES)] | None
    ) = None
    style_notes: Annotated[str | None, Field(max_length=MAX_NOTES_LENGTH)] = None
    avoid_terms: Annotated[list[StylePreference], Field(max_length=MAX_AVOID_TERMS)] | None = None

    default_quality_tier: QualityTier | None = None
    min_output_pixels: Annotated[int, Field(ge=512, le=20000)] | None = None
    require_transparent_background: bool | None = None

    daily_budget: Annotated[BudgetAmount, Field(le=MAX_DAILY_BUDGET)] | None = None
    monthly_budget: Annotated[BudgetAmount, Field(le=MAX_MONTHLY_BUDGET)] | None = None

    weekly_research_enabled: bool | None = None
    weekly_research_weekday: Annotated[int, Field(ge=0, le=6)] | None = None
    weekly_research_hour_utc: Annotated[int, Field(ge=0, le=23)] | None = None
    notify_on_failure: bool | None = None
    notify_on_budget_warning: bool | None = None
    notify_on_approval_needed: bool | None = None

    @field_validator("currency")
    @classmethod
    def _supported_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.upper()
        if upper not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {sorted(SUPPORTED_CURRENCIES)}")
        return upper

    @field_validator("target_marketplace")
    @classmethod
    def _supported_marketplace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lower = value.strip().lower()
        if lower not in SUPPORTED_MARKETPLACES:
            raise ValueError(f"target_marketplace must be one of {sorted(SUPPORTED_MARKETPLACES)}")
        return lower

    @field_validator("target_country")
    @classmethod
    def _upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("style_preferences", "avoid_terms", "default_product_uses")
    @classmethod
    def _strip_and_dedupe(cls, value: list[str] | None) -> list[str] | None:
        """Preserve the owner's order, drop blanks and exact duplicates."""
        if value is None:
            return None
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                result.append(cleaned)
        return result


class StoreCredentialRequest(BaseModel):
    """The one request body that carries a secret. It is never echoed back."""

    model_config = ConfigDict(extra="forbid")

    secret: Annotated[SecretStr, Field(min_length=8, max_length=4096)]
    label: Annotated[str | None, Field(max_length=120)] = None


class CredentialResponse(BaseModel):
    """Metadata only. There is no field here that can hold a decrypted value."""

    provider: ProviderName
    configured: bool
    #: Bullets plus the last four characters, so the owner can identify which
    #: key is stored without the key being readable.
    masked_value: str | None
    label: str | None
    key_version: int | None
    updated_at: str | None


class CredentialListResponse(BaseModel):
    items: list[CredentialResponse]


class TelegramConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paired: bool
    telegram_username: str | None = None
    pairing_code_expires_at: datetime | None = None


class TelegramPairingCodeResponse(BaseModel):
    pairing_code: str
    expires_at: datetime
