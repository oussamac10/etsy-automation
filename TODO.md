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

The roadmap now supports three idea-input modes and private Telegram remote
control. Phase 1 remains complete; no completed work was reopened.

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

- [ ] Add `IdeaMode`: `market-led`, `user-idea`, and `hybrid`
- [ ] Preserve the user's original idea verbatim and separately store the
      researched/optimized concept
- [ ] Entities and value objects: `User`, `ShopConnection`, `ResearchRun`,
      `ResearchEvidence`, `KeywordCluster`, `ProductIdea`, `DesignPrompt`,
      `ArtworkJob`, `Asset`, `Approval`, `ProductionJob`, `Mockup`,
      `IpReview`, `ListingDraft`, `Package`, `ProviderUsage`,
      `AuditEvent`
- [ ] Add Telegram entities/value objects for bot configuration, authorized
      owner identity, message/action correlation, and notification delivery
- [ ] UUID primary keys, UTC timestamps, `Decimal`/minor-unit money
- [ ] SQLAlchemy 2 typed mappings and repositories
- [ ] Alembic migrations, reversible and tested against a fresh database
- [ ] Unique constraints on idempotency keys; one decision per immutable version
- [ ] Persist the workflow state machine with compare-and-set transitions
- [ ] Audit log, provider usage ledger, idempotency records
- [ ] Outbox pattern for job dispatch and Telegram notifications
- [ ] Unit and integration tests for every invariant and cost calculation

## Phase 3 — Authentication and settings

- [ ] Single-owner auth with Argon2id
      ([ADR-0002](docs/adr/0002-single-owner-authentication.md))
- [ ] Sessions and CSRF protection on mutating routes
- [ ] Encrypted provider, Etsy, and Telegram secret/token storage with a
      versioned key
- [ ] Provider settings that never return a secret
- [ ] Budget, quality, target-country, language, style, and product-use defaults
- [ ] Settings for schedules and notification preferences

## Phase 4 — Telegram remote control

- [ ] Private Telegram Bot API adapter and secure webhook endpoint
- [ ] Verify Telegram's webhook secret and allow only the configured owner ID
- [ ] Commands for status, submitting an idea, pausing, resuming, and stopping
      automation
- [ ] Inline buttons for approve, reject, regenerate, edit, and open dashboard
- [ ] Idempotent callback handling, expired-action handling, and audit records
- [ ] Notifications for failures, budget limits, approvals, and completed jobs
- [ ] Fake-adapter integration tests; no real Telegram messages in normal tests

## Phase 5 — Idea input, research, and approval

- [ ] Let the owner choose `market-led`, `user-idea`, or `hybrid`
- [ ] Dashboard form and Telegram command for submitting a personal idea
- [ ] Preserve the original concept while producing a separately optimized
      market position
- [ ] Research seasonal and evergreen demand using at least three buyer-intent
      query angles
- [ ] Real research and OpenAI structured-synthesis adapters (first paid
      providers)
- [ ] Evidence, keyword clusters, scoring, confidence, and prompt generation
- [ ] Generate a complete design prompt and negative prompt for every idea
- [ ] Ranked idea screen, Telegram summary, and **gate 1**
- [ ] Cost estimates, budget enforcement, and low-confidence labelling
- [ ] Relax the `PROVIDER_MODE=live` startup rejection only for configured
      Phase 5 providers

## Phase 6 — Artwork generation and approval

- [ ] OpenAI Image and optional Recraft adapters
- [ ] Queued generation with retry, idempotency, and cost capture
- [ ] Object storage and complete asset provenance
- [ ] Dashboard comparison plus Telegram previews and **gate 2**
- [ ] Approve, reject, or regenerate without duplicate billing

## Phase 7 — PNG production pipeline

- [ ] Alpha/background workflow, safe trim, and upscale
- [ ] Deterministic SVG typography for approved slogans
- [ ] Mockup templates for supported product types
- [ ] Validate dimensions, transparency, margins, spelling, and cropped edges
- [ ] Generate and persist a PNG QA report
- [ ] Send production completion and preview links through Telegram

## Phase 8 — SEO, risk review, and download package

- [ ] Generate Etsy title, description, no more than 13 valid tags, and required
      AI disclosure
- [ ] Store preliminary IP-risk checks, warnings, and human acknowledgement
- [ ] Create licence, customer instructions, manifest, PNG files, and ZIP
- [ ] Listing editor with optimistic concurrency and **gate 3**
- [ ] Send the complete listing/package review to Telegram
- [ ] Never claim legal clearance, profitability, or guaranteed ranking

## Phase 9 — Etsy integration

- [ ] OAuth with PKCE and state
- [ ] Create Etsy draft listings and upload preview images and digital files
- [ ] Rate-limit handling and resumable partial failure
- [ ] Enforce final approval before draft creation
- [ ] Send the draft URL and result to the dashboard and Telegram
- [ ] Keep publication manual; the application must never activate a listing

## Phase 10 — Deployment, scheduling, and monitoring

- [ ] Deploy the web, API, workers, PostgreSQL, Redis, and object storage for
      continuous operation
- [ ] Scheduled research for seasonal and evergreen opportunities
- [ ] Dashboards, error alerts, health monitoring, backups, and restore test
- [ ] Spend caps, monthly usage reports, and cost alerts
- [ ] Telegram daily/weekly reports for jobs, drafts, costs, and available Etsy
      performance data
- [ ] Security review, dependency audit, retention controls, and runbook

## Phase 11 — Optional SaaS expansion

Not before the private tool has real usage evidence.

- [ ] Tenant isolation, team roles, and separate Etsy shops
- [ ] Subscription billing, quotas, and usage metering
- [ ] Etsy Personal/Commercial Access requirements
- [ ] Data export/deletion and support tooling
- [ ] Abuse prevention and public legal pages

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
