# Etsy PNG Automation

A private, single-shop tool that helps one Etsy seller go from research to an
Etsy **draft** listing: research original PNG product ideas, approve a concept,
generate artwork alternatives, approve one artwork, process and package the
files, generate listing SEO, run a preliminary IP review, and create a draft.

**It prepares work. It does not publish.** The application never activates an
Etsy listing, never claims an idea is profitable, and never certifies that a
design or phrase is free of third-party rights.

---

## Status

**Phase 1 — Foundation: complete.** The monorepo, services, health checks,
tooling, CI and fake providers are in place. There is no research, artwork,
production or Etsy integration yet — those arrive in Phases 4–8. See
[`docs/PHASES.md`](docs/PHASES.md) and
[`docs/progress/phase-1-foundation.md`](docs/progress/phase-1-foundation.md).

---

## Quick start

Requirements: Docker with Compose v2, and (for local tooling) Node 24+ with
pnpm 11+ and Python 3.12+.

```bash
cp .env.example .env        # placeholders only; no real key is needed
docker compose up -d --build

# Optional: block until the long-running services report healthy.
# (Waiting on the whole project fails when the one-shot minio-init and
# migrate containers exit, even successfully.)
docker compose up -d --wait api web worker image-worker
```

Then open:

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API health | http://localhost:8000/api/health |
| API docs | http://localhost:8000/api/docs |
| Image worker health | http://localhost:8100/health |
| MinIO console | http://localhost:9001 |

Stop everything with `docker compose down` (add `-v` to drop the volumes).

### Port conflicts

Every host port is configurable, because 5432, 6379 and 3000 are commonly taken.
Set the ones you need in `.env`:

```dotenv
POSTGRES_PORT=55432
REDIS_PORT=56379
WEB_PORT=3300
API_PORT=8800
NUXT_PUBLIC_API_BASE=http://localhost:8800
CORS_ALLOWED_ORIGINS=http://localhost:3300
```

`NUXT_PUBLIC_API_BASE` is read by the browser, so it must use the **host** port,
not the internal one.

---

## Local development without Docker

```bash
# TypeScript workspaces
pnpm install

# Python (one virtualenv for the API and the worker)
python3.12 -m venv .venv
.venv/bin/pip install -e "apps/api[dev]" -e "apps/worker[dev]"
```

Run the pieces individually (PostgreSQL, Redis and MinIO still come from
Compose):

```bash
docker compose up -d postgres redis minio minio-init

cd apps/api && ../../.venv/bin/uvicorn app.main:create_app --factory --reload
cd apps/worker && ../../.venv/bin/dramatiq worker.main
pnpm dev:image-worker
pnpm dev:web
```

Migrations are an explicit step, never implicit on startup:

```bash
cd apps/api && ../../.venv/bin/alembic upgrade head
```

---

## Commands

```bash
# TypeScript
pnpm lint            # ESLint across every workspace, zero warnings allowed
pnpm typecheck       # tsc / vue-tsc per workspace
pnpm test            # Vitest unit tests
pnpm test:e2e        # Playwright against a running stack

# Python
.venv/bin/python -m ruff format --check apps/api apps/worker
.venv/bin/python -m ruff check apps/api apps/worker
cd apps/api    && ../../.venv/bin/python -m mypy . && ../../.venv/bin/python -m pytest
cd apps/worker && ../../.venv/bin/python -m mypy . && ../../.venv/bin/python -m pytest

# Infrastructure
docker compose config --quiet
docker compose up -d --build
docker compose up -d --wait api web worker image-worker
```

`pnpm test:e2e` expects the stack to be running. If you changed the host ports,
point it at them:

```bash
E2E_WEB_URL=http://localhost:3300 E2E_API_URL=http://localhost:8800 pnpm test:e2e
```

---

## Repository layout

```text
apps/
  api/            FastAPI service — routes, domain, ports, fake providers, Alembic
  worker/         Dramatiq worker — retry policy, idempotency keys, broker wiring
  image-worker/   Node/Fastify service wrapping Sharp
  web/            Nuxt 3 + Vue 3 + Pinia + Tailwind
packages/
  domain/         Shared TypeScript workflow vocabulary and Etsy tag rules
  image-pipeline/ Sharp-based validation and inspection library
infra/docker/     Dockerfiles
docs/             Architecture, workflow, costs, phases, progress reports
tests/e2e/        Playwright end-to-end suite
.claude/skills/   Agent skills, including etsy-png-idea-research
```

---

## Workflow and the three gates

```text
RESEARCHING → IDEA_REVIEW → ART_GENERATION → ART_REVIEW
            → PRODUCTION → IP_REVIEW → LISTING_REVIEW → ETSY_DRAFT_CREATED
```

Three decisions always belong to a person and can never be automated:

1. **Idea approval** — a rejected idea never reaches artwork generation.
2. **Artwork approval** — a rejected artwork never enters production.
3. **Trademark acknowledgement and final listing approval** — and even then the
   system creates a draft only.

Every stage has an explicit, retryable failure state. See
[`docs/workflow.md`](docs/workflow.md).

---

## Providers and cost

Phase 1 ships **fake providers only**. `PROVIDER_MODE=live` is rejected at
startup, and no API key is read by any code path. Real adapters arrive with the
phases that own them (research and text: Phase 4, images: Phase 5, Etsy:
Phase 8).

Before implementing any paid provider, read
[`docs/API_COSTS.md`](docs/API_COSTS.md). Prices live in versioned configuration
with an `effective_from` date and a source URL; every paid job is estimated
before dispatch and reconciled against recorded usage afterwards.

---

## Security notes

- No real credential is committed, logged, returned to the browser, or placed in
  a package. `.env` is gitignored; `.env.example` holds placeholders only.
- Placeholder secrets are rejected at startup whenever `APP_ENV` is not `local`.
- Structured logs redact secret-shaped keys, and health checks report an error
  *class* rather than a driver message, because connection strings carry
  passwords.
- Errors are RFC 9457 problem documents; internal exception text never reaches a
  client.
- Image input is bounded by byte, pixel and dimension limits before decoding.

---

## Documentation

| Document | What it covers |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Product rules and engineering constraints (authoritative) |
| [`docs/architecture.md`](docs/architecture.md) | Services, layering, data flow, decisions |
| [`docs/workflow.md`](docs/workflow.md) | The state machine, gates and failure handling |
| [`docs/PHASES.md`](docs/PHASES.md) | Phase plan and acceptance criteria |
| [`docs/API_COSTS.md`](docs/API_COSTS.md) | Provider prices and the budget model |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`TODO.md`](TODO.md) | Current state and the next step |

---

## Etsy API notice

This application is not endorsed by or affiliated with Etsy, Inc. The required
non-endorsement notice must be present before any commercial release.
