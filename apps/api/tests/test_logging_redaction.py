"""Secrets must never reach a log line (root CLAUDE.md, security section)."""

from __future__ import annotations

from app.infrastructure.logging import REDACTED, redact_secrets


def test_top_level_secret_is_redacted() -> None:
    event = redact_secrets(None, "info", {"event": "x", "secret_key": "hunter2"})
    assert event["secret_key"] == REDACTED


def test_nested_secret_is_redacted() -> None:
    event = redact_secrets(
        None,
        "info",
        {"event": "x", "provider": {"api_key": "sk-live-123", "model": "fake"}},
    )
    assert event["provider"]["api_key"] == REDACTED
    assert event["provider"]["model"] == "fake"


def test_deeply_nested_secret_is_redacted() -> None:
    event = redact_secrets(None, "info", {"a": {"b": {"refresh_token": "rt-1", "keep": "yes"}}})
    assert event["a"]["b"]["refresh_token"] == REDACTED
    assert event["a"]["b"]["keep"] == "yes"


def test_connection_strings_are_redacted() -> None:
    event = redact_secrets(
        None,
        "info",
        {"database_url": "postgresql://u:p@h/db", "redis_url": "redis://u:p@h/0"},
    )
    assert event["database_url"] == REDACTED
    assert event["redis_url"] == REDACTED


def test_ordinary_fields_survive() -> None:
    event = redact_secrets(None, "info", {"event": "job_finished", "run_id": "r-1"})
    assert event["event"] == "job_finished"
    assert event["run_id"] == "r-1"


def test_key_matching_is_case_insensitive() -> None:
    event = redact_secrets(None, "info", {"Authorization": "Bearer x"})
    assert event["Authorization"] == REDACTED
