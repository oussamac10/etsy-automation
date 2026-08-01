# TODO

Current state and the next step. Phase detail lives in
[`docs/PHASES.md`](docs/PHASES.md); evidence lives in `docs/progress/`.

## Now

**Phase 1 — Foundation: complete.**
See [`docs/progress/phase-1-foundation.md`](docs/progress/phase-1-foundation.md).
169 tests passing, lint and strict type checks clean, all seven Compose services
healthy, no paid API call made.

**Next: Phase 2 — Domain and persistence.** Not started. Do not begin without an
explicit instruction.

---

## Phase 1 — Foundation ✅

- [x] Monorepo: pnpm workspaces (`apps/web`, `apps/image-worker`, `packages/*`)
      plus two Python projects (`apps/api`, `apps/worker`)
- [x] Nuxt 3 + Vue 3 + TypeScript + Pinia + Tailwind 4
- [x] FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + asyncpg
- [x] Dramatiq worker on Redis ([ADR-0001](docs/adr/0001-queue-dramatiq.md))
- [x] Node image worker: Fastify + Sharp
- [x] PostgreSQL 16, Redis 7, MinIO with bucket bootstrap
- [x] Docker Compose with a health check on every service
- [x] `GET /api/health` plus database, Redis, image-worker and web health checks
- [x] Environment validation at startup (Pydantic Settings and zod)
- [x] Provider ports and deterministic fake adapters
- [x] Workflow state machine, three gates, retryable failure states
- [x] Retry policy and idempotency-key derivation
- [x] RFC 9457 problem details, correlation IDs, secret redaction
- [x] ESLint, Vitest, Ruff, mypy strict, Pytest, Playwright
- [x] GitHub Actions CI: python, migrations, node, compose, e2e, security
- [x] ADRs for the queue, authentication and the two-worker split
- [x] `.env.example`, `.gitignore`, README, architecture and workflow docs
- [x] `.claude/skills/etsy-png-idea-research/SKILL.md`

## Phase 2 — Domain and persistence

- [ ] Entities and value objects: `User`, `ShopConnection`, `ResearchRun`,
      `ResearchEvidence`, `KeywordCluster`, `ProductIdea`, `DesignPrompt`,
      `ArtworkJob`, `Asset`, `Approval`, `ProductionJob`, `Mockup`, `IpReview`,
      `ListingDraft`, `Package`, `ProviderUsage`, `AuditEvent`
- [ ] UUID primary keys, UTC timestamps, `Decimal`/minor-unit money
- [ ] SQLAlchemy 2 typed mappings and repositories
- [ ] Alembic migrations, reversible and tested against a fresh database
- [ ] Unique constraints on idempotency keys; one decision per immutable version
- [ ] Persist the workflow state machine with compare-and-set transitions
- [ ] Audit log, provider usage ledger, idempotency records
- [ ] Outbox pattern for job dispatch
- [ ] Unit and integration tests for every invariant and cost calculation

## Phase 3 — Authentication and settings

- [ ] Single-owner auth with Argon2id
      ([ADR-0002](docs/adr/0002-single-owner-authentication.md))
- [ ] Sessions, CSRF protection on mutating routes
- [ ] Encrypted token storage with a versioned key
- [ ] Provider settings that never return a secret
- [ ] Budget and quality defaults

## Phase 4 — Research and idea approval

- [ ] Research brief UI and API
- [ ] Real research and OpenAI synthesis adapters (first paid provider)
- [ ] Evidence, keyword clusters, scoring, prompt generation
- [ ] Ranked idea screen and **gate 1**
- [ ] Cost estimates and low-confidence labelling
- [ ] Relax the `PROVIDER_MODE=live` startup rejection

## Phase 5 — Artwork generation and approval

- [ ] OpenAI Image and Recraft adapters
- [ ] Queued generation with retry, idempotency and cost capture
- [ ] Object storage and provenance
- [ ] Comparison UI and **gate 2**

## Phase 6 — Production pipeline

- [ ] Alpha and background workflow, safe trim, upscale
- [ ] Deterministic SVG typography
- [ ] Mockup templates
- [ ] PNG QA report

## Phase 7 — SEO, legal review, and package

- [ ] Title, description, ≤13 valid tags, AI disclosure
- [ ] Preliminary IP records and acknowledgement
- [ ] Licence, instructions, manifest, ZIP
- [ ] Listing editor with optimistic concurrency and **gate 3**

## Phase 8 — Etsy integration

- [ ] OAuth with PKCE and state
- [ ] Draft listing, image and digital-file upload
- [ ] Rate-limit handling and resumable partial failure

## Phase 9 — Operations

- [ ] Dashboards, alerts, backups, restore test
- [ ] Spend caps and monthly usage report
- [ ] Security review, dependency audit, retention controls

## Phase 10 — Optional SaaS expansion

Not before the private tool has real usage evidence.

---

## Carried-over items from Phase 1

Small things that were deliberately deferred rather than forgotten:

- [ ] Commit the generated OpenAPI document and generate frontend types from it
      (currently the web app hand-writes zod schemas)
- [ ] Give `pnpm audit` and `pip-audit` a triage policy so CI can stop using
      `continue-on-error`
- [ ] Adopt `@nuxt/test-utils` so components can rely on Nuxt auto-imports in
      unit tests
- [ ] Read-only root filesystems and explicit CPU/memory limits on containers
- [ ] Add the Etsy API non-endorsement notice to the UI before any release
