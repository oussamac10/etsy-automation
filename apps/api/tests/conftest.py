"""Shared fixtures.

Every test runs with a fake provider mode and placeholder secrets. Nothing here
may reach a paid API or a real database.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.settings import Settings

TEST_ENV: dict[str, str] = {
    "APP_ENV": "local",
    "LOG_LEVEL": "ERROR",
    "SECRET_KEY": "test-secret-key",
    # Long enough for the ENCRYPTION_KEY length rule. Obviously not a real key.
    "ENCRYPTION_KEY": "test-encryption-key-not-a-real-key-0123456789",
    "DATABASE_URL": "postgresql+asyncpg://etsy:etsy@localhost:5432/etsy_test",
    "REDIS_URL": "redis://localhost:6379/1",
    "PROVIDER_MODE": "fake",
    "IMAGE_WORKER_URL": "http://image-worker.invalid:8100",
}


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    yield TEST_ENV


@pytest.fixture
def settings(test_env: dict[str, str]) -> Settings:
    return Settings()
