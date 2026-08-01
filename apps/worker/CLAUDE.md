# CLAUDE.md — Background Worker

These rules extend the root instructions for `apps/worker`.

## Responsibilities

- Research queries and AI synthesis
- Artwork generation
- Background removal/upscale/vectorization requests
- Local image QA and mockup rendering
- Licence/instructions/manifest generation
- ZIP packaging
- Etsy draft creation and uploads
- Scheduled analytics synchronization after MVP

## Job rules

- Delivery is at least once; every handler must be idempotent.
- Use a stable job ID and operation-specific idempotency key.
- Acquire a bounded lease and renew it for long jobs.
- Persist heartbeat, attempt count, progress, provider request ID, and cost.
- Check cancellation before expensive stages.
- Retry only classified transient failures.
- Respect `retry-after`; otherwise exponential backoff with jitter.
- Move exhausted jobs to a visible failed state; never loop forever.
- A retry may reuse completed artifacts only after checksum and provenance validation.
- Do not dispatch a paid child job if its parent gate is not approved.

## Observability

- Structured logs contain job ID, correlation ID, run ID, provider, operation, duration, status, and cost.
- Metrics include queue latency, runtime, retries, provider errors, budget rejects, and cost by operation.
- Do not log secrets, OAuth tokens, complete provider responses, or binary payloads.

## Testing

- Test duplicate message delivery and worker crash after provider success but before local commit.
- Test timeouts, rate limits, cancellation, budget exhaustion, and partial Etsy upload recovery.
- Use fake clock and deterministic providers.

