# TODO

Current state and the next step. Phase detail lives in
[`docs/PHASES.md`](docs/PHASES.md); evidence lives in `docs/progress/`.

## Now

**Phase 1 — Foundation: complete.**
See [`docs/progress/phase-1-foundation.md`](docs/progress/phase-1-foundation.md).

**Phase 2 — Domain and persistence: complete.**
See [`docs/progress/phase-2-domain-database.md`](docs/progress/phase-2-domain-database.md).
18 tables, one reversible migration, 351 tests passing, lint and strict type
checks clean, no paid API call made.

**Phase 3 — Authentication and settings: complete.**
See [`docs/progress/phase-3-auth-settings.md`](docs/progress/phase-3-auth-settings.md)
and [`docs/authentication-and-secrets.md`](docs/authentication-and-secrets.md).
Three new tables, one reversible migration, 419 API tests passing, lint and
strict type checks clean, no paid API call made.

**Next: Phase 4 — Telegram remote control.** Not started. Do not begin without
an explicit instruction.

The roadmap now supports three idea-input modes and private Telegram remote
control. Phases 1 and 2 remain complete; no completed work was reopened.

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

## Phase 2 — Domain and persistence ✅

- [x] Add `IdeaMode`: `market-led`, `user-idea`, and `hybrid`
- [x] Preserve the user's original idea verbatim and separately store the
      researched/optimized concept
- [x] Entities and value objects: `User`, `ProductWorkflow`, `OriginalIdea`(+
      revisions), `ResearchRun`, `ResearchEvidence`, `KeywordCluster`,
      `ProductConcept`, `DesignPrompt`, `ArtworkJob`, `Asset`, `Approval`,
      `ProductionJob`, `ListingDraft`, `ProviderUsage`, `AuditEvent`,
      `WorkflowTransition`, `WorkflowFailure`
      ([name mapping](docs/domain-model.md#naming-the-specs-areas-mapped-to-entities))
- [x] UUID primary keys, UTC timestamps, `Decimal`/minor-unit money
- [x] SQLAlchemy 2 typed mappings and repositories
- [x] Alembic migration, reversible and tested against a fresh database
- [x] Unique constraints on idempotency keys; approvals record the reviewed
      version
- [x] Persist the workflow state machine with compare-and-set transitions
- [x] Audit log and provider usage ledger
- [x] Unit and integration tests for every invariant and cost calculation
- [x] Minimal workflow API and deterministic development fixtures

Deferred from this phase, with reasons in the progress report:

- [ ] `ShopConnection` — encryption now exists (Phase 3); the table belongs with
      the Etsy OAuth flow (Phase 9)
- [ ] Telegram entities — Phase 4
- [ ] `Mockup`, `Package`, standalone `IpReview` — Phase 7/8
- [ ] Outbox pattern — needs a real dispatcher (Phase 4/5)
- [ ] Run the integration suite in CI (`TEST_DATABASE_URL` wiring)

## Phase 3 — Authentication and settings ✅

- [x] Enforce ownership on every workflow route, derived from the session and
      never from the request body; cross-owner access answers `404`
- [x] Single-owner auth with Argon2id
      ([ADR-0002](docs/adr/0002-single-owner-authentication.md))
- [x] Sessions and CSRF protection on mutating routes
- [x] Encrypted provider secret storage with a versioned key and a rotation
      command that loses nothing
      ([design](docs/authentication-and-secrets.md))
- [x] Provider settings that never return a secret
- [x] Budget, quality, target-country, language, style, and product-use defaults
- [x] Settings for schedules and notification preferences
- [x] Two development owners, so ownership isolation is demonstrable

Deferred from this phase, with reasons in the progress report:

- [ ] `ShopConnection` — belongs with the Etsy OAuth flow (Phase 9); the cipher
      and key-version column are ready for it
- [ ] Telegram bot token storage — belongs with the adapter (Phase 4)
- [ ] Frontend login, logout and settings screens — no frontend bullet in this
      phase and no protected endpoint is called yet; they land with the
      dashboard (Phase 5)

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
