from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from app.api.auth_schemas import (
    LoginRequest,
    StoreCredentialRequest,
    UpdateSettingsRequest,
)
from app.domain.enums import IdeaMode
from app.domain.owner_settings import BudgetRelationError, validate_budgets
from app.settings import Settings


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "APP_ENV": "local",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-not-a-real-key-0123456789",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    base.update(overrides)
    return base


def _build(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    for key, value in _env(**overrides).items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_valid_local_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(monkeypatch)
    assert settings.app_env == "local"
    assert settings.provider_mode == "fake"
    assert settings.is_local is True


def test_missing_required_variable_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _env():
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_log_level_is_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _build(monkeypatch, LOG_LEVEL="debug").log_level == "DEBUG"


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        _build(monkeypatch, LOG_LEVEL="chatty")


def test_blocking_database_driver_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="asyncpg"):
        _build(monkeypatch, DATABASE_URL="postgresql://u:p@localhost:5432/db")


def test_placeholder_secret_is_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        _build(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="dev-only-insecure-secret-key-change-me",
        )


def test_placeholder_secret_is_allowed_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(monkeypatch, SECRET_KEY="dev-only-insecure-secret-key-change-me")
    assert settings.app_env == "local"


def test_live_provider_mode_is_allowed_without_telegram_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build(monkeypatch, PROVIDER_MODE="live")
    assert settings.provider_mode == "live"
    assert settings.telegram_bot_token is None


def test_secrets_are_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(monkeypatch, SECRET_KEY="super-sensitive-value")
    assert "super-sensitive-value" not in repr(settings)
    assert "super-sensitive-value" not in str(settings)
    assert settings.secret_key.get_secret_value() == "super-sensitive-value"


def test_short_encryption_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Too little entropy to derive a credential key from."""
    with pytest.raises(ValidationError, match="ENCRYPTION_KEY must be at least"):
        _build(monkeypatch, ENCRYPTION_KEY="too-short")


def test_session_cookie_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(monkeypatch)
    assert settings.session_cookie_name == "etsy_session"
    assert settings.session_ttl_hours == 12
    # Off locally so plain-HTTP localhost works; forced on everywhere else.
    assert settings.session_cookie_secure is False


def test_insecure_session_cookie_is_refused_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        _build(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="a-real-looking-production-secret-key",
            SESSION_COOKIE_SECURE="false",
        )


def test_cors_origins_are_split(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(monkeypatch, CORS_ALLOWED_ORIGINS="http://a.test, http://b.test ,")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"ENCRYPTION_KEY_PREVIOUS": "the-retired-key-0123456789012345678901"},
        {"ENCRYPTION_KEY_PREVIOUS_VERSION": "1", "ENCRYPTION_KEY_VERSION": "2"},
    ],
)
def test_a_rotation_needs_both_halves(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str]
) -> None:
    with pytest.raises(ValidationError, match="together"):
        _build(monkeypatch, **overrides)


def test_a_rotation_must_move_the_version_forward(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="lower than ENCRYPTION_KEY_VERSION"):
        _build(
            monkeypatch,
            ENCRYPTION_KEY_PREVIOUS="the-retired-key-0123456789012345678901",
            ENCRYPTION_KEY_PREVIOUS_VERSION="1",
            ENCRYPTION_KEY_VERSION="1",
        )


def test_a_valid_rotation_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build(
        monkeypatch,
        ENCRYPTION_KEY_PREVIOUS="the-retired-key-0123456789012345678901",
        ENCRYPTION_KEY_PREVIOUS_VERSION="1",
        ENCRYPTION_KEY_VERSION="2",
    )
    assert settings.encryption_key_previous_version == 1
    assert "retired-key" not in repr(settings)


# --- Owner settings schemas & budget rules ---------------------------------


def test_a_daily_budget_below_the_monthly_one_is_fine() -> None:
    validate_budgets(Decimal("2.00"), Decimal("30.00"))
    validate_budgets(Decimal("30.00"), Decimal("30.00"))


def test_a_daily_budget_above_the_monthly_one_is_rejected() -> None:
    with pytest.raises(BudgetRelationError, match="never bind"):
        validate_budgets(Decimal("40.00"), Decimal("30.00"))


def test_an_empty_update_changes_nothing() -> None:
    assert UpdateSettingsRequest().model_dump(exclude_unset=True) == {}


def test_only_the_sent_fields_are_present() -> None:
    payload = UpdateSettingsRequest(default_language="fr")
    assert payload.model_dump(exclude_unset=True) == {"default_language": "fr"}


def test_an_unknown_field_is_a_validation_error_not_a_silent_no_op() -> None:
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(target_curency="USD")  # type: ignore[call-arg]


def test_currency_is_normalised_and_restricted() -> None:
    assert UpdateSettingsRequest(currency="eur").currency == "EUR"
    with pytest.raises(ValidationError, match="currency must be one of"):
        UpdateSettingsRequest(currency="XYZ")


def test_marketplace_is_restricted() -> None:
    assert UpdateSettingsRequest(target_marketplace="Etsy").target_marketplace == "etsy"
    with pytest.raises(ValidationError, match="target_marketplace must be one of"):
        UpdateSettingsRequest(target_marketplace="Amazon")


def test_idea_mode_is_restricted() -> None:
    assert (
        UpdateSettingsRequest(default_idea_mode=IdeaMode.MARKET_LED).default_idea_mode
        == IdeaMode.MARKET_LED
    )
    with pytest.raises(ValidationError):
        UpdateSettingsRequest(default_idea_mode="invalid-mode")  # type: ignore[arg-type]


def test_invalid_credentials_are_rejected() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="invalid-email", password=SecretStr("short"))
    with pytest.raises(ValidationError):
        StoreCredentialRequest(secret=SecretStr("short"))
