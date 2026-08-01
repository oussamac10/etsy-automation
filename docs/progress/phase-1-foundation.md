# Phase 1 — Foundation

**Status:** Complete
**Date:** 2026-08-01
**Next phase:** Phase 2 — Domain and persistence (not started)

## Acceptance criteria

> All services start locally; health checks, lint, types, and starter tests pass
> without paid keys.

Met. Evidence below.

| Checklist item | Status | Evidence |
|---|---|---|
| Monorepo structure and pinned runtime versions | Done | pnpm workspaces + two Python projects; every dependency pinned exactly (Python) or with a caret and a lockfile (Node) |
| Nuxt, FastAPI, worker, PostgreSQL, Redis, MinIO | Done | 7 services in `compose.yaml`, all reported healthy |
| Docker Compose health checks | Done | Health check on every long-running service; `depends_on` waits on `service_healthy` / `service_completed_successfully` |
| Formatting, lint, type checks, tests, CI | Done | `ruff format`, `ruff check`, `mypy --strict`, `pytest`, `eslint --max-warnings=0`, `tsc`/`vue-tsc`, `vitest`, `playwright`; six CI jobs |
| Configuration validation and fake providers | Done | Pydantic Settings and zod both fail the process on an invalid environment; fake adapters for every port |
| ADRs for queue and authentication | Done | ADR-0001, ADR-0002, plus ADR-0003 for the two-worker split |

## What was built

### Services

| Service | Stack | Port | Health |
|---|---|---|---|
| `web` | Nuxt 3.21, Vue 3.5, Pinia 3, Tailwind 4 | 3000 | `GET /api/_health` |
| `api` | FastAPI 0.141, Python 3.12, SQLAlchemy 2.0, Alembic | 8000 | `GET /api/health`, `GET /api/health/live` |
| `worker` | Dramatiq 2.2 on Redis | — | `python -m worker.healthcheck` |
| `image-worker` | Node 24, Fastify 5, Sharp 0.35 | 8100 | `GET /health`, `GET /health/live` |
| `postgres` | PostgreSQL 16.10 | 5432 | `pg_isready` |
| `redis` | Redis 7.4 | 6379 | `redis-cli ping` |
| `minio` | MinIO + `minio-init` bucket job | 9000/9001 | `mc ready local` |

### Packages

- `packages/domain` — shared TypeScript workflow vocabulary and Etsy tag rules.
- `packages/image-pipeline` — Sharp-based decode guards, image inspection and a
  libvips self-test.

### Domain and policy code

- `app/domain/workflow.py` — the authoritative state machine: linear transitions,
  three ungated-by-design human gates, explicit retryable failure states, and no
  published/active state anywhere.
- `app/ports/` — all eight provider protocols plus a `Clock`, and a normalised
  `ProviderError` taxonomy that carries the retry decision.
- `app/providers/fake.py` — deterministic fakes for every port.
- `worker/retry.py` — exponential backoff with jitter, `retry-after` honoured,
  permanent failures never retried.
- `worker/idempotency.py` — stable, input-derived keys scoped by run.

### Cross-cutting

- Correlation IDs accepted or minted per request and echoed on responses, in both
  the API and the image worker.
- RFC 9457 problem details for every error; unhandled exceptions return a generic
  message.
- structlog/pino redaction of secret-shaped keys at any nesting depth.
- Alembic baseline revision, proven by an upgrade → downgrade → upgrade CI job.

## Verification

All commands run on 2026-08-01.

### Tests

| Suite | Command | Result |
|---|---|---|
| API | `cd apps/api && pytest` | **74 passed** |
| Worker | `cd apps/worker && pytest` | **23 passed** |
| `@etsy/domain` | `vitest run` | **16 passed** |
| `@etsy/image-pipeline` | `vitest run` | **8 passed** |
| `@etsy/image-worker` | `vitest run` | **17 passed** |
| `@etsy/web` | `vitest run` | **20 passed** |
| End-to-end | `pnpm test:e2e` against the running stack | **11 passed** |

**169 tests, all passing.**

### Static analysis

| Check | Result |
|---|---|
| `ruff format --check` (api, worker) | clean |
| `ruff check` (api, worker) | All checks passed |
| `mypy --strict` (api) | no issues in 31 source files |
| `mypy --strict` (worker) | no issues in 8 source files |
| `eslint . --max-warnings=0` | clean |
| `tsc --noEmit` (3 packages) + `vue-tsc --noEmit` (web) | clean |

### Runtime

`docker compose up -d --build --wait` reached healthy on all seven services.

```json
GET /api/health → 200
{
  "status": "ok", "service": "api", "version": "0.1.0", "app_env": "local",
  "components": {
    "database":     {"status": "ok", "latency_ms": 1},
    "redis":        {"status": "ok", "latency_ms": 0},
    "image_worker": {"status": "ok", "latency_ms": 3}
  }
}
```

```json
GET /health (image worker) → 200
{"status":"ok","service":"image-worker","components":{"sharp":{"status":"ok","latencyMs":4},"redis":{"status":"ok","latencyMs":1}}}
```

`docker compose config --quiet` passes.

### Browser verification

The dashboard was loaded in Chromium via the Playwright MCP server against the
running containers. The accessibility tree showed live data fetched from the API
across origins — all four components reporting *Healthy* with latencies, the
eight workflow states in order, and the three gates — with **zero console errors
or warnings**.

## Deliberate deviations

1. **Both `apps/worker` and `apps/image-worker` exist.** The Phase 1 request
   named `apps/image-worker`; the repository's existing `apps/worker/CLAUDE.md`
   describes the Python queue worker. These are different services, so both were
   built. Recorded as [ADR-0003](../adr/0003-two-workers.md).

2. **No module-level `app` instance in `app/main.py`.** Importing the module must
   not read the environment, so uvicorn uses
   `app.main:create_app --factory`.

3. **`PROVIDER_MODE=live` is rejected at startup.** No real adapter exists yet, so
   a stray environment variable cannot start paid traffic. This validation must
   be relaxed in Phase 4/5 when the first real adapter lands.

4. **Vue formatting rules disabled in ESLint.** `vue/max-attributes-per-line` and
   `vue/singleline-html-element-content-newline` are formatting concerns and
   there is no Vue formatter in the toolchain; leaving them on would produce
   warnings that never fail a build. Lint now runs with `--max-warnings=0`.

## Known limitations

- **No entities or tables.** The Alembic baseline is empty by design; the domain
  model lands in Phase 2.
- **No authentication.** ADR-0002 records the decision; implementation is Phase 3.
- **No real providers.** Every adapter is a fake. No API key is read by any code
  path.
- **The worker has no actors yet** beyond `heartbeat`. Real jobs arrive with the
  phases that own them.
- **Object storage is wired but unused.** MinIO runs and the bucket is created;
  the `ObjectStorage` port only has an in-memory implementation.
- **`pnpm audit` and `pip-audit` are `continue-on-error` in CI.** They report
  without blocking until a triage policy exists.
- **Web unit tests do not use `@nuxt/test-utils`.** Components under test import
  `computed` explicitly rather than relying on auto-imports.

## Cost impact

**Zero.** No paid API was called at any point. `PROVIDER_MODE=fake` is the
default and `live` is rejected; `PAID_SMOKE_TEST_ENABLED=false` everywhere
including CI. Ongoing cost is local compute only.

## Next step

Phase 2 — Domain and persistence. Do not start it without an explicit
instruction.
