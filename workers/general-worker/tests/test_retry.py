from __future__ import annotations

import random

import pytest

from app.ports.errors import ProviderError, ProviderErrorKind
from worker.retry import DEFAULT_POLICY, BackoffPolicy, retry_after, should_retry


def _error(kind: ProviderErrorKind, retry_after_seconds: float | None = None) -> ProviderError:
    return ProviderError(
        kind=kind,
        provider="fake",
        operation="op",
        message="m",
        retry_after_seconds=retry_after_seconds,
    )


class TestShouldRetry:
    @pytest.mark.parametrize("kind", [ProviderErrorKind.RETRYABLE, ProviderErrorKind.RATE_LIMITED])
    def test_transient_failures_are_retried(self, kind: ProviderErrorKind) -> None:
        assert should_retry(_error(kind), attempt=1) is True

    @pytest.mark.parametrize(
        "kind",
        [
            ProviderErrorKind.INVALID_REQUEST,
            ProviderErrorKind.AUTHENTICATION,
            ProviderErrorKind.BUDGET_EXCEEDED,
            ProviderErrorKind.PERMANENT,
        ],
    )
    def test_permanent_failures_are_not_retried(self, kind: ProviderErrorKind) -> None:
        assert should_retry(_error(kind), attempt=1) is False

    def test_unclassified_errors_are_not_retried(self) -> None:
        """An unexpected bug must not burn budget in a retry loop."""
        assert should_retry(RuntimeError("boom"), attempt=1) is False

    def test_attempts_are_capped(self) -> None:
        error = _error(ProviderErrorKind.RETRYABLE)
        assert should_retry(error, attempt=DEFAULT_POLICY.max_attempts) is False


class TestBackoff:
    def test_delay_grows_exponentially(self) -> None:
        policy = BackoffPolicy(base_seconds=1.0, factor=2.0, jitter=0.0)
        assert policy.delay_for(1) == pytest.approx(1.0)
        assert policy.delay_for(2) == pytest.approx(2.0)
        assert policy.delay_for(3) == pytest.approx(4.0)

    def test_delay_is_capped(self) -> None:
        policy = BackoffPolicy(base_seconds=1.0, factor=10.0, max_seconds=30.0, jitter=0.0)
        assert policy.delay_for(10) == pytest.approx(30.0)

    def test_jitter_stays_within_bounds(self) -> None:
        policy = BackoffPolicy(base_seconds=4.0, factor=1.0, jitter=0.5)
        rng = random.Random(7)  # noqa: S311 - deterministic test seed
        for _ in range(50):
            delay = policy.delay_for(1, rng=rng)
            assert 2.0 <= delay <= 6.0

    def test_jitter_actually_varies(self) -> None:
        policy = BackoffPolicy(base_seconds=4.0, jitter=0.5)
        rng = random.Random(1)  # noqa: S311
        delays = {policy.delay_for(1, rng=rng) for _ in range(20)}
        assert len(delays) > 1

    def test_invalid_attempt_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            DEFAULT_POLICY.delay_for(0)


class TestRetryAfter:
    def test_provider_retry_after_wins(self) -> None:
        error = _error(ProviderErrorKind.RATE_LIMITED, retry_after_seconds=12.0)
        assert retry_after(error, attempt=1) == 12.0

    def test_provider_retry_after_is_capped(self) -> None:
        policy = BackoffPolicy(max_seconds=30.0)
        error = _error(ProviderErrorKind.RATE_LIMITED, retry_after_seconds=9999.0)
        assert retry_after(error, attempt=1, policy=policy) == 30.0

    def test_falls_back_to_backoff(self) -> None:
        error = _error(ProviderErrorKind.RETRYABLE)
        assert retry_after(error, attempt=1) > 0
