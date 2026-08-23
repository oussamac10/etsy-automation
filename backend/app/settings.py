"""Environment configuration, validated once at startup.

An invalid or unsafe environment must stop the process. In particular the
placeholder secrets shipped in ``.env.example`` are rejected outside ``local``
so a development key can never reach staging or production.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.security import MIN_ENCRYPTION_KEY_LENGTH

AppEnv = Literal["local", "staging", "production"]
ProviderMode = Literal["fake", "live"]

# Values shipped in .env.example. Usable locally, never anywhere else.
PLACEHOLDER_SECRETS = frozenset(
    {
        "dev-only-insecure-secret-key-change-me",
        "dev-only-insecure-encryption-key-change-me",
        "change-me",
    }
)


class Settings(BaseSettings):
    """Application settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=None,  # Compose and the dev script export the variables.
        extra="ignore",
        case_sensitive=True,
        frozen=True,
    )

    app_env: AppEnv = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")  # noqa: S104
    api_port: int = Field(default=8000, ge=1, le=65535, alias="API_PORT")

    secret_key: SecretStr = Field(alias="SECRET_KEY")
    encryption_key: SecretStr = Field(alias="ENCRYPTION_KEY")
    encryption_key_version: int = Field(default=1, ge=1, alias="ENCRYPTION_KEY_VERSION")
    #: The key being retired. Set both of these during a rotation so rows written
    #: under the old key stay readable until `python -m app.rotate_encryption_key`
    #: has re-encrypted them; unset them afterwards.
    encryption_key_previous: SecretStr | None = Field(default=None, alias="ENCRYPTION_KEY_PREVIOUS")
    encryption_key_previous_version: int | None = Field(
        default=None, ge=1, alias="ENCRYPTION_KEY_PREVIOUS_VERSION"
    )
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:3300", alias="CORS_ALLOWED_ORIGINS"
    )

    # --- Session cookie (ADR-0002) -----------------------------------------
    session_cookie_name: str = Field(default="etsy_session", alias="SESSION_COOKIE_NAME")
    #: 12 hours. Long enough for a working session, short enough that a stolen
    #: cookie is not indefinitely useful.
    session_ttl_hours: int = Field(default=12, ge=1, le=720, alias="SESSION_TTL_HOURS")
    #: Defaults to False only so plain-HTTP localhost works; the validator below
    #: forces it on outside `local`, where a cookie sent over HTTP is a bug.
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    queue_broker: Literal["dramatiq"] = Field(default="dramatiq", alias="QUEUE_BROKER")
    queue_namespace: str = Field(default="etsy_automation", alias="QUEUE_NAMESPACE")

    s3_endpoint_url: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT_URL")
    s3_public_endpoint_url: str | None = Field(default=None, alias="S3_PUBLIC_ENDPOINT_URL")
    s3_bucket: str = Field(default="etsy-assets", alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_access_key_id: str = Field(default="minioadmin", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(
        default=SecretStr("minioadmin"), alias="S3_SECRET_ACCESS_KEY"
    )
    s3_force_path_style: bool = Field(default=True, alias="S3_FORCE_PATH_STYLE")

    image_worker_url: str = Field(default="http://localhost:8100", alias="IMAGE_WORKER_URL")

    provider_mode: ProviderMode = Field(default="fake", alias="PROVIDER_MODE")
    default_run_budget_usd: str = Field(default="1.00", alias="DEFAULT_RUN_BUDGET_USD")
    monthly_budget_usd: str = Field(default="30.00", alias="MONTHLY_BUDGET_USD")
    paid_smoke_test_enabled: bool = Field(default=False, alias="PAID_SMOKE_TEST_ENABLED")

    telegram_bot_token: SecretStr | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: SecretStr | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    image_max_input_bytes: int = Field(default=150 * 1024 * 1024, alias="IMAGE_MAX_INPUT_BYTES")
    image_max_pixels: int = Field(default=100_000_000, alias="IMAGE_MAX_PIXELS")

    # --- Refinement and Generation Models ---
    recraft_generation_model: str = Field(default="recraftv4_1", alias="RECRAFT_GENERATION_MODEL")
    recraft_refinement_model: str = Field(default="recraftv3", alias="RECRAFT_REFINEMENT_MODEL")
    recraft_refinement_strength: float = Field(
        default=0.20, ge=0.0, le=1.0, alias="RECRAFT_REFINEMENT_STRENGTH"
    )
    gemini_refinement_model: str = Field(
        default="gemini-3.1-flash-image", alias="GEMINI_REFINEMENT_MODEL"
    )

    # --- Etsy Integration (Phase 9) ---
    etsy_api_key: SecretStr | None = Field(default=None, alias="ETSY_API_KEY")
    etsy_client_id: SecretStr | None = Field(default=None, alias="ETSY_CLIENT_ID")
    etsy_shared_secret: SecretStr | None = Field(default=None, alias="ETSY_SHARED_SECRET")
    etsy_client_secret: SecretStr | None = Field(default=None, alias="ETSY_CLIENT_SECRET")
    etsy_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/etsy/callback", alias="ETSY_REDIRECT_URI"
    )
    etsy_api_base_url: str = Field(default="https://openapi.etsy.com/v3", alias="ETSY_API_BASE_URL")
    etsy_authorization_url: str = Field(
        default="https://www.etsy.com/oauth/connect", alias="ETSY_AUTHORIZATION_URL"
    )
    etsy_token_url: str = Field(
        default="https://api.etsy.com/v3/public/oauth/token", alias="ETSY_TOKEN_URL"
    )
    etsy_frontend_redirect_url: str = Field(
        default="http://localhost:3000/settings", alias="ETSY_FRONTEND_REDIRECT_URL"
    )
    etsy_scopes: str = Field(default="listings_r listings_w shops_r shops_w", alias="ETSY_SCOPES")

    @field_validator("etsy_redirect_uri", mode="before")
    @classmethod
    def _default_redirect_uri(cls, value: object) -> str:
        if not value or not str(value).strip():
            return "http://localhost:8800/api/v1/auth/etsy/callback"
        return str(value).strip()

    @field_validator("etsy_frontend_redirect_url", mode="before")
    @classmethod
    def _default_frontend_redirect_url(cls, value: object) -> str:
        if not value or not str(value).strip():
            return "http://localhost:3300/settings"
        return str(value).strip()

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// driver; "
                "blocking drivers stall the event loop."
            )
        return value

    @model_validator(mode="after")
    def _reject_unsafe_combinations(self) -> Settings:
        if self.app_env != "local":
            for name, secret in (
                ("SECRET_KEY", self.secret_key),
                ("ENCRYPTION_KEY", self.encryption_key),
            ):
                if secret.get_secret_value() in PLACEHOLDER_SECRETS:
                    raise ValueError(
                        f"{name} still holds the .env.example placeholder; "
                        f"generate a real value for APP_ENV={self.app_env}."
                    )
        # An application key shorter than this has too little entropy to derive
        # a credential-encryption key from (app/infrastructure/security.py).
        if len(self.encryption_key.get_secret_value()) < MIN_ENCRYPTION_KEY_LENGTH:
            raise ValueError(
                f"ENCRYPTION_KEY must be at least {MIN_ENCRYPTION_KEY_LENGTH} characters. "
                'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )
        # Half a rotation is worse than none: the old key without its version
        # cannot be matched to a row, and the version without the key is a lie.
        if (self.encryption_key_previous is None) != (self.encryption_key_previous_version is None):
            raise ValueError(
                "ENCRYPTION_KEY_PREVIOUS and ENCRYPTION_KEY_PREVIOUS_VERSION must be set together."
            )
        if (
            self.encryption_key_previous_version is not None
            and self.encryption_key_previous_version >= self.encryption_key_version
        ):
            raise ValueError(
                "ENCRYPTION_KEY_PREVIOUS_VERSION must be lower than ENCRYPTION_KEY_VERSION; "
                "bump ENCRYPTION_KEY_VERSION when you change ENCRYPTION_KEY."
            )
        # TELEGRAM_BOT_TOKEN can be loaded from DB, so we do not
        # enforce it being present in the env at startup.
        if self.app_env != "local" and not self.session_cookie_secure:
            raise ValueError(
                "SESSION_COOKIE_SECURE must be true outside APP_ENV=local; a "
                "session cookie sent over plain HTTP is interceptable."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def resolved_etsy_api_key(self) -> str | None:
        key = self.etsy_api_key or self.etsy_client_id
        if key is not None:
            val = key.get_secret_value().strip()
            return val if val else None
        return None

    @property
    def resolved_etsy_shared_secret(self) -> str | None:
        secret = self.etsy_shared_secret or self.etsy_client_secret
        if secret is not None:
            val = secret.get_secret_value().strip()
            return val if val else None
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance used as a FastAPI dependency."""
    # Values come from the environment; pydantic-settings fills every field.
    return Settings()
