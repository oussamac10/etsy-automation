# Architecture

How the system is put together, and why. Product rules live in
[`../CLAUDE.md`](../CLAUDE.md); this document explains the shape of the code.

## Services

| Service | Technology | Responsibility |
|---|---|---|
| `web` | Nuxt 3, Vue 3, Pinia, Tailwind 4 | Owner UI: briefs, ranked ideas, the three approval gates, listing editor |
| `api` | FastAPI, Python 3.12, SQLAlchemy 2 | HTTP surface, orchestration, domain invariants, persistence |
| `worker` | Dramatiq on Redis | Every slow or paid operation: research, generation, production, packaging, Etsy calls |
| `image-worker` | Node 24, Fastify, Sharp | Image validation, inspection, and later trimming, typography and mockups |
| `postgres` | PostgreSQL 16 | System of record |
| `redis` | Redis 7 | Queue broker. Never the system of record |
| `minio` | MinIO (S3-compatible) | Binary assets. Never stored in PostgreSQL |

Two separate workers exist because they do different work in different runtimes.
`worker` orchestrates jobs and talks to providers in Python, next to the domain
model. `image-worker` exists because the image pipeline is built on Sharp and
SVG templates, which are Node libraries. The API calls it over HTTP.

## Layering inside the API

```text
api/routes  →  application/use_cases  →  domain
                        ↓
                  ports/protocols
                        ↑
              infrastructure + provider adapters
```

- **Routes** parse, authenticate, authorise, call one use case, and map the
  result. No business logic.
- **Use cases** own orchestration and transaction boundaries.
- **Domain** (`app/domain/`) owns invariants and state transitions. It imports
  no framework, no ORM, no HTTP client and no provider SDK.
- **Ports** (`app/ports/`) are the interfaces the application depends on.
- **Adapters** (`app/infrastructure/`, `app/providers/`) implement the ports.

The dependency arrow always points inwards. A provider SDK type must never
appear in a domain signature.

### Ports defined in Phase 1

`ResearchProvider`, `TextGenerationProvider`, `ImageGenerationProvider`,
`ImageProcessingProvider`, `ObjectStorage`, `EtsyGateway`,
`TrademarkDataGateway`, `CostCalculator`, `Clock`.

Every adapter normalises its failures into one `ProviderError` category —
`retryable`, `rate_limited`, `authentication`, `invalid_request`,
`budget_exceeded` or `permanent` — so the retry decision is made in one place
(`worker/retry.py`) instead of per provider. Anything unclassified is treated as
permanent, so a bug cannot spend money in a retry loop.

`EtsyGateway` deliberately has no publish or activate method. The capability
does not exist in the type system, which is stronger than a policy comment.

## The TypeScript/Python boundary

The workflow state machine is authoritative in Python
(`apps/api/src/app/domain/workflow.py`). `packages/domain/src/workflow.ts`
mirrors the names so the web app and image worker are typed against the same
vocabulary, and `apps/api/tests/test_workflow_contract.py` parses the TypeScript
file and fails if the two drift.

The web app does not hard-code the pipeline. It reads `GET /api/v1/workflow`, so
the UI can never advertise a stage the backend does not implement. The local
list is a fallback for when the API is unreachable.

## Data flow (target design)

```text
brief  →  research job  →  evidence + clusters + scored ideas  →  IDEA GATE
       →  artwork jobs   →  asset alternatives                  →  ARTWORK GATE
       →  production job →  QA report + package
       →  IP review      →  listing draft                       →  LISTING GATE
       →  Etsy draft (never published)
```

Every arrow that costs money or takes time is a queued job with an idempotency
key, a retry policy, a timeout and a cost ceiling. Job state is persisted before
and after each external call, and a database transaction is never held open
across a network request.

## Configuration

Configuration comes from environment variables and is validated at startup, in
every runtime:

- `apps/api/src/app/settings.py` (Pydantic Settings)
- `apps/image-worker/src/config.ts` (zod)

Both fail the process on an invalid environment rather than surfacing an
`undefined` at request time. Two rules are enforced in code:

1. The `.env.example` placeholder secrets are rejected whenever `APP_ENV` is not
   `local`.
2. `PROVIDER_MODE=live` is rejected outright until the phase that integrates a
   real provider, so a stray environment variable cannot start paid traffic.

## Health checks

| Endpoint | Meaning |
|---|---|
| `GET /api/health/live` | The API process is up. Touches nothing else |
| `GET /api/health` | Readiness: PostgreSQL, Redis and the image worker, each probed independently |
| `GET /health/live` (image worker) | The Node process is up |
| `GET /health` (image worker) | libvips can actually encode a PNG, and Redis answers |
| `GET /api/_health` (web) | The Nitro server is up. Deliberately does not call the API |
| `python -m worker.healthcheck` | The Dramatiq worker can reach its broker |

Readiness returns 503 when any component is down, and reports the failing
component's error **class** only — driver messages embed the DSN, and the DSN
contains the password. The Sharp check encodes a real PNG, because importing the
module succeeds even when its platform binary is missing.

## Observability

Structured logging (structlog for Python, pino for Node) with a
`x-correlation-id` accepted or minted per request and echoed on the response, so
a single ID follows a request across web → api → worker → image-worker. A
redaction processor drops secret-shaped keys at any nesting depth, so logging a
settings object cannot leak an encryption key.

## Security posture

- Binary assets go to object storage, never PostgreSQL; content hashes detect
  duplicates.
- Image input is bounded by byte, pixel and dimension limits **before** decoding.
- SVG is excluded from accepted input formats; it is only ever rendered through
  the hardened typography path (Phase 6).
- Errors are RFC 9457 problem documents. Unhandled exceptions return a generic
  message; the detail goes to the log.
- Containers run as a non-root user. `allowBuilds` in `pnpm-workspace.yaml`
  limits install scripts to `esbuild` and `sharp`.

## Decisions

Recorded as ADRs in [`adr/`](adr/):

- [ADR-0001](adr/0001-queue-dramatiq.md) — Dramatiq over Celery for the queue
- [ADR-0002](adr/0002-single-owner-authentication.md) — Single-owner
  authentication with Argon2id
- [ADR-0003](adr/0003-two-workers.md) — Two worker processes rather than one

## What Phase 1 does not include

No entities or tables beyond the Alembic baseline, no authentication, no
research, no artwork generation, no production pipeline, no Etsy integration,
and no real provider adapter. Those are Phases 2–8.
