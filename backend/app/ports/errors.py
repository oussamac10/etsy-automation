"""Normalised provider failures.

Every adapter maps its SDK/HTTP errors onto exactly one of these categories so
retry policy lives in one place instead of per provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderErrorKind(StrEnum):
    RETRYABLE = "retryable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    BUDGET_EXCEEDED = "budget_exceeded"
    NOT_FOUND = "not_found"
    PERMANENT = "permanent"


#: Only these categories may be retried. A 4xx invalid request never is.
RETRYABLE_KINDS = frozenset({ProviderErrorKind.RETRYABLE, ProviderErrorKind.RATE_LIMITED})


@dataclass(frozen=True, slots=True)
class ProviderError(Exception):
    """A provider failure with a retry decision already made."""

    kind: ProviderErrorKind
    provider: str
    operation: str
    message: str
    #: Seconds the provider asked us to wait, when it said so.
    retry_after_seconds: float | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.provider}/{self.operation}] {self.kind}: {self.message}"

    @property
    def is_retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS
