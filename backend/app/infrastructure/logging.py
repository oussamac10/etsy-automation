"""Structured logging.

Logs are JSON outside ``local``. Secrets are dropped by a processor rather than
by discipline alone, because a single careless ``log.info(settings)`` would
otherwise print an encryption key.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "secret_key",
        "encryption_key",
        "password",
        "authorization",
        "api_key",
        "openai_api_key",
        "recraft_api_key",
        "etsy_client_secret",
        "access_token",
        "refresh_token",
        "token",
        "database_url",
        "redis_url",
        "s3_secret_access_key",
    }
)

REDACTED = "[redacted]"


def redact_secrets(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Replace the value of any sensitive key anywhere in the event."""
    import os

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")

    def _redact_value(val: Any) -> Any:
        if isinstance(val, str):
            if tg_token and tg_token in val:
                return val.replace(tg_token, "[REDACTED_TELEGRAM_TOKEN]")
            return val
        elif isinstance(val, dict):
            return _redact_mapping(val)
        elif isinstance(val, list):
            return [_redact_value(item) for item in val]
        return val

    def _redact_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
        return {
            key: (REDACTED if key.lower() in SENSITIVE_KEYS else _redact_value(value))
            for key, value in mapping.items()
        }

    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level, logging.INFO))

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
