# Implementation Phases

Claude must complete one phase, verify it, update this file, and stop.

## Phase 1 — Foundation ✅ complete 2026-08-01

- [x] Monorepo structure and pinned runtime versions
- [x] Nuxt, FastAPI, worker, PostgreSQL, Redis, MinIO
- [x] Docker Compose health checks
- [x] Formatting, lint, type checks, tests, CI
- [x] Configuration validation and fake providers
- [x] Architecture decision records for queue and authentication

Acceptance: all services start locally; health checks, lint, types, and starter
tests pass without paid keys.

Evidence: `docs/progress/phase-1-foundation.md`. All seven Compose services
reached healthy; 169 tests pass (74 API, 23 worker, 61 TypeScript unit, 11
end-to-end); `ruff check`, `ruff format --check`, `mypy --strict`, `eslint
--max-warnings=0`, `tsc`/`vue-tsc` and `docker compose config` are clean. No
paid API was called.

## Phase 2 — Domain and persistence

- [ ] Core entities, value objects, and persisted workflow state machine
- [ ] `IdeaMode` with `market-led`, `user-idea`, and `hybrid`
- [ ] Immutable original user idea plus separately optimized concept/version
- [ ] Telegram configuration, authorized owner, action, and delivery records
- [ ] PostgreSQL repositories and reversible Alembic migrations
- [ ] Audit log, provider usage ledger, idempotency records, and outbox
- [ ] Unit and integration tests

Acceptance: every gate/state invariant and cost calculation is tested; every
research run records its input mode; a supplied idea can be retrieved exactly as
entered after an optimized version is created.

## Phase 3 — Authentication and settings

- [ ] Single-owner authentication
- [ ] Provider settings without exposing secrets
- [ ] Budget, quality, marketplace, language, and style defaults
- [ ] Encrypted provider, Etsy, and Telegram secret/token storage
- [ ] Schedule and notification preferences

Acceptance: unauthorized access is rejected, sensitive values never return
through APIs, and encrypted secrets can be rotated without data loss.

## Phase 4 — Telegram remote control

- [ ] Private Telegram bot adapter and secure webhook
- [ ] Webhook-secret verification and owner-ID allow-list
- [ ] Commands for status, idea submission, pause, resume, and stop
- [ ] Inline approval, rejection, regeneration, edit, and dashboard buttons
- [ ] Idempotent callbacks, expiry handling, audit trail, and delivery retries
- [ ] Failure, budget, approval, and completion notifications

Acceptance: fake-provider E2E proves that an unauthorized sender is rejected,
duplicate callbacks change state once, and the owner can submit an idea and
control a run without any real Telegram call.

## Phase 5 — Idea input, research, and approval

- [ ] Dashboard and Telegram inputs for all three idea modes
- [ ] Market-led seasonal and evergreen discovery
- [ ] User-idea validation that preserves the original concept
- [ ] Hybrid research that combines the original idea with current evidence
- [ ] Research provider and OpenAI structured-synthesis adapter
- [ ] Evidence, keyword clusters, scoring, confidence, and prompt generation
- [ ] Complete positive and negative design prompts for every idea
- [ ] Ranked idea screen, Telegram summary, cost estimate, and approval gate

Acceptance: fake-provider E2E covers `market-led`, `user-idea`, and `hybrid`;
each run produces at least three evidence-linked, ranked concepts with complete
prompts; the faithful user-idea version remains recognizable and unchanged in
the original-input record.

## Phase 6 — Artwork generation and approval

- [ ] OpenAI Image and optional Recraft adapters
- [ ] Queued generation jobs, retry/idempotency/cost capture
- [ ] Object storage and provenance
- [ ] Artwork comparison UI, Telegram previews, and approval gate
- [ ] Approve, reject, and regenerate actions

Acceptance: mocked E2E generates two alternatives, sends preview metadata to the
owner, and proves duplicate requests are billed once in the ledger.

## Phase 7 — PNG production pipeline

- [ ] Validation, alpha/background workflow, safe trim, and upscale
- [ ] Deterministic typography for approved slogans
- [ ] Mockup templates
- [ ] PNG QA report and approval preview
- [ ] Telegram production-complete notification

Acceptance: fixture-based tests prove dimensions, alpha, margins, spelling,
hashes, and malicious-input rejection.

## Phase 8 — SEO, risk review, and download package

- [ ] Listing title, description, no more than 13 valid tags, and AI disclosure
- [ ] Preliminary phrase/IP-risk records and human acknowledgement
- [ ] Licence, instructions, manifest, PNG files, and reproducible ZIP
- [ ] Listing review UI with optimistic concurrency and final approval gate
- [ ] Complete review summary through Telegram

Acceptance: the package is reproducible, Etsy rules are configurable rather
than scattered constants, and neither the UI nor Telegram can label an item
legally cleared or guaranteed profitable.

## Phase 9 — Etsy integration

- [ ] Seller App OAuth with PKCE/state
- [ ] Draft listing, preview-image upload, and digital-file upload
- [ ] Rate-limit handling and resumable partial failure
- [ ] Final approval enforcement before draft creation
- [ ] Draft result and URL delivered through dashboard and Telegram
- [ ] No publish/activate capability

Acceptance: staging/test flow creates one draft only, never activates it, and
resumes safely after simulated failure.

## Phase 10 — Deployment, scheduling, and monitoring

- [ ] Continuous deployment for all application services
- [ ] Scheduled seasonal and evergreen research
- [ ] Dashboards, alerts, backups, and restore test
- [ ] Spend caps, cost alerts, and monthly usage report
- [ ] Telegram job, failure, draft, cost, and performance summaries
- [ ] Security review, dependency audit, retention controls, and runbook

Acceptance: the production checklist is signed off; rollback and restore are
documented and tested; scheduled work continues without the owner's computer;
budget and operational failures produce actionable Telegram alerts.

## Phase 11 — Optional SaaS expansion

Do not begin until the private single-shop MVP has real usage evidence.

- [ ] Tenant isolation and team roles
- [ ] Separate Etsy shops, bot identities, and notification preferences
- [ ] Etsy Personal/Commercial Access requirements
- [ ] Subscription billing, quotas, and usage metering
- [ ] Data export/deletion and support tooling
- [ ] Abuse prevention and public legal pages
