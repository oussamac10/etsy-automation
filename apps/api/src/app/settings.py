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
    cors_allowed_origins: str = Field(default="http://localhost:3000", alias="CORS_ALLOWED_ORIGINS")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    queue_broker: Literal["dramatiq"] = Field(default="dramatiq", alias="QUEUE_BROKER")
    queue_namespace: str = Field(default="etsy_automation", alias="QUEUE_NAMESPACE")

    s3_endpoint_url: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(default="etsy-assets", alias="S3_BUCKET")

    image_worker_url: str = Field(default="http://localhost:8100", alias="IMAGE_WORKER_URL")

    provider_mode: ProviderMode = Field(default="fake", alias="PROVIDER_MODE")
    default_run_budget_usd: str = Field(default="1.00", alias="DEFAULT_RUN_BUDGET_USD")
    monthly_budget_usd: str = Field(default="30.00", alias="MONTHLY_BUDGET_USD")
    paid_smoke_test_enabled: bool = Field(default=False, alias="PAID_SMOKE_TEST_ENABLED")

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
        # Phase 1 has no real provider adapters. Refusing "live" here means a
        # stray environment variable cannot start a paid integration early.
        if self.provider_mode == "live":
            raise ValueError(
                "PROVIDER_MODE=live is not supported yet. Real provider adapters "
                "arrive in Phase 4/5; keep PROVIDER_MODE=fake."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings instance used as a FastAPI dependency."""
    # Values come from the environment; pydantic-settings fills every field.
    return Settings()
