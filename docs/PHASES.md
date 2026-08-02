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

## Phase 2 — Domain and persistence ✅ complete 2026-08-02

- [x] Core entities, value objects, and persisted workflow state machine
- [x] `IdeaMode` with `market-led`, `user-idea`, and `hybrid`
- [x] Immutable original user idea plus separately optimized concept/version
- [x] PostgreSQL repositories and a reversible Alembic migration
- [x] Audit log and provider usage ledger
- [x] Unit and integration tests

Deferred with reasons: Telegram records (Phase 4), `ShopConnection` (Phase 3,
needs encrypted tokens), and the outbox (Phase 4/5, needs a real dispatcher).

Acceptance: every gate/state invariant and cost calculation is tested; every
research run records its input mode; a supplied idea can be retrieved exactly as
entered after an optimized version is created.

Evidence: `docs/progress/phase-2-domain-database.md`. 18 tables; migration
`0002_phase_2_domain` upgrades, downgrades and re-upgrades cleanly with no model
drift; 351 tests pass (261 API, 23 worker, 67 TypeScript unit); `ruff`,
`mypy --strict`, `eslint --max-warnings=0`, `tsc`/`vue-tsc` and
`docker compose config` are clean. No paid API was called.

## Phase 3 — Authentication and settings ✅ complete 2026-08-02

- [x] Single-owner authentication (Argon2id, server-side session cookie, CSRF)
- [x] Ownership enforcement derived from the session, never from the client
- [x] Provider settings without exposing secrets
- [x] Budget, quality, marketplace, language, and style defaults
- [x] Encrypted provider secret storage with a working key rotation
- [x] Schedule and notification preferences

Deferred with reasons:

- **Etsy and Telegram token storage.** `ShopConnection` needs the OAuth flow it
  belongs to (scopes, refresh rotation, shop ID), and the Telegram bot token
  belongs to the adapter in Phase 4. The cipher, the key-version column and the
  rotation command are in place for both; only the tables are outstanding.
- **Frontend authentication UI.** This phase has no frontend bullet, and the web
  app consumes no protected endpoint today (only `/api/health` and the static
  `/api/v1/workflow`). Login, logout and settings screens land with the
  dashboard in Phase 5 rather than being invented ahead of the screens they
  belong to.

Acceptance: unauthorized access is rejected, sensitive values never return
through APIs, and encrypted secrets can be rotated without data loss.

Evidence: `docs/progress/phase-3-auth-settings.md` and
`docs/authentication-and-secrets.md`. Migration `0003_phase_3_auth_settings`
upgrades, downgrades and re-upgrades cleanly on a fresh database; 419 API tests
pass (233 unit, 186 integration) plus 23 worker, 67 TypeScript unit and 11
end-to-end; `ruff`, `mypy --strict`, `eslint --max-warnings=0`, `tsc`/`vue-tsc`
and `docker compose config` are clean. No paid API was called.

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
