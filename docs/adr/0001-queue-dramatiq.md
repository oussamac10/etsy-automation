# ADR-0001 — Use Dramatiq on Redis for the queue

- **Status**: Accepted
- **Date**: 2026-08-01
- **Phase**: 1

## Context

Phase 1 must choose between Dramatiq and Celery and document the decision. Every
slow or paid operation runs as a queued job, and each job needs an idempotency
key, a retry policy, a timeout and a cost ceiling. Delivery is at least once, so
handlers must be idempotent regardless of which library we pick.

The workload is small — one owner, one shop, tens of listings a month — but each
job is expensive in money rather than CPU. What matters is that retry behaviour
is predictable and easy to reason about, not that the broker scales.

## Decision

Use **Dramatiq** with the Redis broker.

## Why

- **Smaller surface.** Dramatiq's middleware model is a short, readable list
  (`AgeLimit`, `TimeLimit`, `ShutdownNotifications`, `Callbacks`, `Retries`).
  Celery's configuration space is much larger, and most of it addresses problems
  this project does not have.
- **Retries stay ours.** The retry decision belongs in `worker/retry.py`, keyed
  off the normalised `ProviderError` category, because retrying a paid image
  generation on a 4xx would cost money for nothing. Dramatiq's `Retries`
  middleware is a hard ceiling above that logic rather than a competing policy.
- **Redis is already required** as the broker for the image worker's health
  check and for future rate-limit coordination. Celery would work on Redis too,
  but would tempt us toward RabbitMQ semantics we do not need.
- **Predictable defaults.** Dramatiq's at-least-once delivery and explicit time
  limits match the invariants we already have to enforce.

## Consequences

- Every actor must be idempotent. The idempotency key is derived from job inputs
  (`worker/idempotency.py`), so duplicate delivery cannot double-bill.
- Dramatiq ships no type information, so `apps/worker` carries one targeted
  `type: ignore[no-untyped-call]` at the broker constructor and a mypy override
  for `dramatiq.*`. Everything else stays strictly typed.
- Redis is a broker, not a system of record. Job state is persisted to
  PostgreSQL before and after each external call.
- Scheduled work (the optional weekly research run) will need
  `dramatiq-crontab` or an external scheduler; Dramatiq has no built-in beat.

## Alternatives considered

- **Celery** — more features, far more configuration, and a retry model that
  invites us to spread policy across decorators. Rejected as heavier than the
  problem.
- **arq / RQ** — lighter still, but weaker middleware and time-limit stories.
- **PostgreSQL-backed queue** — one fewer service, but polling latency and
  lock contention for no real benefit while Redis is already present.

## Revisit when

Throughput requires multiple worker hosts, or scheduled jobs become central
enough that a first-class scheduler matters.
