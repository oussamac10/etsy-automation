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

**Phase 4 — Telegram remote control: complete.**
See [`docs/progress/phase-4-telegram-remote-control.md`](docs/progress/phase-4-telegram-remote-control.md).
One new table, one reversible migration, 427 backend tests passing, 30 frontend tests passing, lint and type checks clean.

**Phase 5 — Idea input, research, and approval: complete.**
Campaign creation forms, opportunity scores, keyword clusters, risk scans, design prompt revisions, and Gate 1 human approvals via Nuxt 3 dashboard and Telegram Bot inline query callbacks. 471 backend tests and 23 worker tests passing, ruff and mypy strict clean on both Python projects, vue-tsc typechecks clean.

**Next: Phase 6 — Artwork generation and approval.** Not started. Do not begin without
an explicit instruction.

---

## Phase 1 — Foundation ✅

- [x] Monorepo: pnpm workspaces (`frontend`, `workers/image-worker`, `packages/*`)
      plus two Python projects (`backend`, `workers/general-worker`)
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
- [x] Frontend login, logout and settings screens — no frontend bullet in this
      phase and no protected endpoint is called yet; they land with the
      dashboard (Phase 5)

## Phase 4 — Telegram remote control ✅

- [x] Private Telegram Bot API adapter and secure webhook
- [x] Verify Telegram's webhook secret and allow only the paired owner ID
- [x] Commands for status, pausing, resuming, and stopping (cancelling) automation
- [x] Idempotent callback/update handling, pairing code expiration, and audit records
- [x] Fake-adapter integration tests; no real Telegram messages in normal tests
- [x] Inline buttons for approve, reject, regenerate, edit, and open dashboard (deferred to land with approval screens)
- [ ] Notifications for failures, budget limits, approvals, and completed jobs (deferred to land with queue dispatches)

## Phase 5 — Idea input, research, and approval ✅

- [x] Let the owner choose `market-led`, `user-idea`, or `hybrid`
- [x] Dashboard form and Telegram command for submitting a personal idea
- [x] Preserve the original concept while producing a separately optimized
      market position
- [x] Research seasonal and evergreen demand using at least three buyer-intent
      query angles
- [x] Real research and OpenAI structured-synthesis adapters (first paid
      providers)
- [x] Evidence, keyword clusters, scoring, confidence, and prompt generation
- [x] Generate a complete design prompt and negative prompt for every idea
- [x] Ranked idea screen, Telegram summary, and **gate 1**
- [x] Cost estimates, budget enforcement, and low-confidence labelling
- [x] Relax the `PROVIDER_MODE=live` startup rejection only for configured
      Phase 5 providers

Hardening after the first Phase 5 pass:

- [x] One budget rule (`app/application/research.py`) and one phrase screen
      (`app/domain/ip_risk.py`), shared by the API and the worker instead of
      duplicated in both
- [x] `decide_gate` checks ownership before it confirms a concept exists, and
      raises mapped domain errors (409) instead of bare `ValueError` (500)
- [x] Outbox claims rows with `FOR UPDATE SKIP LOCKED`, so a second API replica
      cannot publish the same message
- [x] `CurrentMessage` middleware installed on the broker; the retry path read
      the attempt count through a `dramatiq` attribute that does not exist
- [x] End-to-end tests for `run_research_task` against PostgreSQL: happy path,
      duplicate delivery, missing run, budget refusal, and the permanent versus
      transient error split

## Phase 6 — Artwork generation and approval

- [x] Recraft V4.1 (Primary) and Gemini (Secondary fallback) adapters
- [x] Queued generation with retry, idempotency, and cost capture
- [x] Object storage and complete asset provenance
- [x] Dashboard comparison plus Telegram previews and **gate 2**
- [x] Approve, reject, or regenerate without duplicate billing

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
