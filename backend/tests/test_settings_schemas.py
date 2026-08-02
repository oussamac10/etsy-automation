"""Settings validation at the API boundary and the budget rule below it."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.auth_schemas import (
    CredentialResponse,
    LoginRequest,
    StoreCredentialRequest,
    UpdateSettingsRequest,
)
from app.domain.owner_settings import BudgetRelationError, validate_budgets

# --- The cross-field budget rule -------------------------------------------


def test_a_daily_budget_below_the_monthly_one_is_fine() -> None:
    validate_budgets(Decimal("2.00"), Decimal("30.00"))
    # Equal is allowed: a single-run month is a legitimate configuration.
    validate_budgets(Decimal("30.00"), Decimal("30.00"))


def test_a_daily_budget_above_the_monthly_one_is_rejected() -> None:
    with pytest.raises(BudgetRelationError, match="never bind"):
        validate_budgets(Decimal("40.00"), Decimal("30.00"))


# --- Partial updates -------------------------------------------------------


def test_an_empty_update_changes_nothing() -> None:
    assert UpdateSettingsRequest().model_dump(exclude_unset=True) == {}


def test_only_the_sent_fields_are_present() -> None:
    payload = UpdateSettingsRequest(default_language="fr")
    assert payload.model_dump(exclude_unset=True) == {"default_language": "fr"}


def test_an_unknown_field_is_a_validation_error_not_a_silent_no_op() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(target_curency="USD")  # type: ignore[call-arg]


# --- Vocabulary ------------------------------------------------------------


def test_currency_is_normalised_and_restricted() -> None:
    assert UpdateSettingsRequest(currency="eur").currency == "EUR"
    with pytest.raises(ValidationError, match="currency must be one of"):
        UpdateSettingsRequest(currency="XYZ")


def test_marketplace_is_restricted() -> None:
    assert UpdateSettingsRequest(target_marketplace="Etsy").target_marketplace == "etsy"
    with pytest.raises(ValidationError, match="target_marketplace must be one of"):
        UpdateSettingsRequest(target_marketplace="amazon")


def test_country_is_upper_cased_and_shape_checked() -> None:
    assert UpdateSettingsRequest(target_country="gb").target_country == "GB"
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(target_country="GBR")


# --- Numbers ---------------------------------------------------------------


def test_budgets_stay_decimal_and_two_places() -> None:
    payload = UpdateSettingsRequest(daily_budget=Decimal("2.50"))
    assert payload.daily_budget == Decimal("2.50")
    assert isinstance(payload.daily_budget, Decimal)


def test_a_third_decimal_place_is_rejected() -> None:
    """Storage is minor units; a fraction of a cent has nowhere to go."""
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(daily_budget=Decimal("2.005"))


def test_negative_and_oversized_budgets_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(daily_budget=Decimal("-1.00"))
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(monthly_budget=Decimal("10000.01"))


def test_pixel_and_schedule_bounds() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(min_output_pixels=100)
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(weekly_research_weekday=7)
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(weekly_research_hour_utc=24)


# --- Collections -----------------------------------------------------------


def test_style_preferences_are_trimmed_and_deduped_in_order() -> None:
    payload = UpdateSettingsRequest(style_preferences=[" line art ", "Line Art", "vintage"])
    assert payload.style_preferences == ["line art", "vintage"]


def test_a_blank_style_preference_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(style_preferences=[""])


def test_too_many_style_preferences_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(style_preferences=[f"style {n}" for n in range(21)])


# --- Secrets in schemas ----------------------------------------------------


def test_a_password_is_not_printable_from_the_request_model() -> None:
    request = LoginRequest(email="owner@example.invalid", password="hunter2-hunter2")
    assert "hunter2" not in repr(request)
    assert "hunter2" not in str(request)
    assert request.password.get_secret_value() == "hunter2-hunter2"


def test_a_credential_secret_is_not_printable_either() -> None:
    request = StoreCredentialRequest(secret="sk-super-secret-value")
    assert "sk-super-secret-value" not in repr(request)


def test_the_credential_response_has_no_field_that_could_hold_a_value() -> None:
    """A regression guard: adding a plaintext field here must fail a test."""
    assert set(CredentialResponse.model_fields) == {
        "provider",
        "configured",
        "masked_value",
        "label",
        "key_version",
        "updated_at",
    }


def test_a_malformed_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="whatever-long-enough")
