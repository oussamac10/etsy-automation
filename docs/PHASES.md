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

## Phase 4 — Telegram remote control ✅ complete 2026-08-03

- [x] Private Telegram bot adapter and secure webhook
- [x] Webhook-secret verification and owner-ID allow-list
- [x] Commands for status, pause, resume, and stop (cancel)
- [x] Idempotent updates, pairing expiry handling, and audit trail

Acceptance: fake-provider E2E and integration tests prove that an unauthorized sender is rejected, duplicate updates process once, and the owner can connect their account and control runs without any real Telegram call.

Evidence: `docs/progress/phase-4-telegram-remote-control.md`. Migration `0004_phase_4_telegram` upgrades and downgrades cleanly; 427 backend tests passing, 30 frontend tests passing; frontend dashboard authentication flow and settings page remote control integration complete and verified.

## Phase 5 — Idea input, research, and approval

- [x] Dashboard and Telegram inputs for all three idea modes
- [x] Market-led seasonal and evergreen discovery
- [x] User-idea validation that preserves the original concept
- [x] Hybrid research that combines the original idea with current evidence
- [x] Research provider and OpenAI structured-synthesis adapter
- [x] Evidence, keyword clusters, scoring, confidence, and prompt generation
- [x] Complete positive and negative design prompts for every idea
- [x] Ranked idea screen, Telegram summary, cost estimate, and approval gate

Acceptance: fake-provider E2E covers `market-led`, `user-idea`, and `hybrid`;
each run produces at least three evidence-linked, ranked concepts with complete
prompts; the faithful user-idea version remains recognizable and unchanged in
the original-input record.

Evidence: 471 backend tests and 23 worker tests passing; ruff and mypy strict
clean on both Python projects; no paid provider reachable from the suite.
`tests/integration/test_worker_research_task.py` drives `run_research_task`
against PostgreSQL and covers the happy path, at-least-once redelivery, a
message for a missing run, budget refusal, and the permanent versus transient
error split. `tests/integration/test_api_idea_approval.py` covers Gate 1:
idempotent enqueue, stale-version rejection, and a high-risk concept that can
be rejected but not approved. Budget and phrase-screen rules are unit-tested in
`tests/integration/test_research_budget.py` and `tests/test_ip_risk.py`.

Gap: the actor E2E covers `market-led` and `user-idea`; `hybrid` is exercised at
the domain and repository level only (`tests/test_ideas.py`).

## Phase 6 — Artwork generation and approval ✅ complete 2026-08-14

- [x] Recraft V4.1 (Primary) and Gemini (Secondary fallback) adapters
- [x] Queued generation jobs, retry/idempotency/cost capture
- [x] Object storage and provenance
- [x] Artwork comparison UI, Telegram previews, and approval gate
- [x] Approve, reject, and regenerate actions

Acceptance: mocked E2E generates two alternatives, sends preview metadata to the
owner, and proves duplicate requests are billed once in the ledger.

Evidence: All 234 integration tests passing (including new test suite in `tests/integration/test_artwork.py` verifying end-to-end S3 uploads, budget gates, candidate queries, refinement flows, and Gate 2 state transitions).

## Phase 7 — PNG production pipeline ✅ complete 2026-08-16

- [x] Validation, alpha/background workflow, safe trim (8%), and upscale (4500×5400 px @ 300 DPI)
- [x] Deterministic typography for approved slogans
- [x] User-uploaded mockup template library and 2D canvas compositor
- [x] Structured automated PNG QA report and approval preview
- [x] Telegram production-complete notification with master preview and QA summary
- [x] Zero runtime dummy mockups and dynamic product tabs (categories with count > 0)
- [x] Candidate switching without full-page reloads and non-overlapping recursive polling

Acceptance: fixture-based tests prove dimensions, alpha, margins, spelling,
hashes, and malicious-input rejection. Full monorepo test coverage passes (398 tests).

Evidence: `docs/progress/phase-7-png-production-pipeline.md`.

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

## Phase 11 — Post-publishing profit intelligence and winner expansion

Do not begin until Etsy publishing is working and the shop has enough real sales data to produce meaningful signals. This phase is intentionally lower priority than completing the publishing MVP.

- [ ] Import Etsy orders, transactions, refunds, fees, and listing performance into an owner-scoped analytics model
- [ ] Calculate revenue, net profit, margin, API/design cost per listing, and profit per campaign
- [ ] Rank niches, styles, seasons, keyword clusters, buyer segments, and product themes by actual shop performance
- [ ] AI profit advisor that explains what is working, what is underperforming, and concrete actions to improve profit
- [ ] Detect winning listings and extract reusable performance patterns without copying the original artwork
- [ ] `Winner Expansion` workflow that proposes differentiated ideas based on best sellers
- [ ] Generate new PNG concepts from winning patterns and route approved ideas back through the existing research, artwork, production, SEO, and trademark gates
- [ ] Guardrails against near-duplicate designs, trademark reuse, overfitting to tiny samples, and blind automatic publishing
- [ ] Dashboard for sales, profit, conversion signals, winners, losers, and recommendation history
- [ ] Feed validated sales-performance signals back into Phase 5 research scoring so future campaigns learn from real shop results

Acceptance: the system can explain why it recommends a new product using measurable shop evidence; recommendations are advisory until approved by the owner; new artwork is materially differentiated from prior winners; and no automatic publish action is introduced.

## Phase 12 — Optional SaaS expansion

Do not begin until the private single-shop MVP has real usage evidence.

- [ ] Tenant isolation and team roles
- [ ] Separate Etsy shops, bot identities, and notification preferences
- [ ] Etsy Personal/Commercial Access requirements
- [ ] Subscription billing, quotas, and usage metering
- [ ] Data export/deletion and support tooling
- [ ] Abuse prevention and public legal pages