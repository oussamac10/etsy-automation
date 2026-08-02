"""Retry policy.

One implementation, used by every actor, so backoff behaviour cannot drift
between jobs. Permanent 4xx failures are never retried (root CLAUDE.md).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.ports.errors import ProviderError


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    base_seconds: float = 1.0
    factor: float = 2.0
    max_seconds: float = 300.0
    max_attempts: int = 5
    #: Full jitter fraction applied to the computed delay.
    jitter: float = 0.5

    def delay_for(self, attempt: int, *, rng: random.Random | None = None) -> float:
        """Exponential backoff with jitter. ``attempt`` is 1-based."""
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        raw = min(self.base_seconds * (self.factor ** (attempt - 1)), self.max_seconds)
        source = rng or random.Random()  # noqa: S311 - jitter, not cryptography
        spread = raw * self.jitter
        return max(0.0, raw - spread + source.random() * 2 * spread)


DEFAULT_POLICY = BackoffPolicy()


def should_retry(error: Exception, attempt: int, policy: BackoffPolicy = DEFAULT_POLICY) -> bool:
    """Decide whether an actor may run again.

    Only errors an adapter classified as transient qualify; anything unclassified
    is treated as permanent so a bug cannot burn the budget in a retry loop.
    """
    if attempt >= policy.max_attempts:
        return False
    if isinstance(error, ProviderError):
        return error.is_retryable
    return False


def retry_after(error: Exception, attempt: int, policy: BackoffPolicy = DEFAULT_POLICY) -> float:
    """Honour a provider's ``retry-after`` when it gave one."""
    if isinstance(error, ProviderError) and error.retry_after_seconds is not None:
        return min(error.retry_after_seconds, policy.max_seconds)
    return policy.delay_for(attempt)
