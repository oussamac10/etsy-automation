# Implementation Phases

Claude must complete one phase, verify it, update this file, and stop.

## Phase 1 — Foundation ✅ complete 2026-08-01

- [x] Monorepo structure and pinned runtime versions
- [x] Nuxt, FastAPI, worker, PostgreSQL, Redis, MinIO
- [x] Docker Compose health checks
- [x] Formatting, lint, type checks, tests, CI
- [x] Configuration validation and fake providers
- [x] Architecture decision records for queue and authentication

Acceptance: all services start locally; health checks, lint, types, and starter tests pass without paid keys.

Evidence: `docs/progress/phase-1-foundation.md`. All seven Compose services
reached healthy; 169 tests pass (74 API, 23 worker, 61 TypeScript unit, 11
end-to-end); `ruff check`, `ruff format --check`, `mypy --strict`, `eslint
--max-warnings=0`, `tsc`/`vue-tsc` and `docker compose config` are clean. No
paid API was called.

## Phase 2 — Domain and persistence

- [ ] Core entities, value objects, workflow state machine
- [ ] PostgreSQL repositories and Alembic migrations
- [ ] Audit log, provider usage ledger, idempotency records
- [ ] Unit and integration tests

Acceptance: every gate/state invariant and cost calculation is tested.

## Phase 3 — Authentication and settings

- [ ] Single-owner authentication
- [ ] Provider settings without exposing secrets
- [ ] Budget and quality defaults
- [ ] Encrypted secret/token storage

Acceptance: unauthorized access is rejected and sensitive values never return through APIs.

## Phase 4 — Research and idea approval

- [ ] Research brief UI/API
- [ ] Research provider and OpenAI structured synthesis adapter
- [ ] Evidence, keyword cluster, scoring, prompt generation
- [ ] Ranked idea screen and approval gate
- [ ] Cost estimates and low-confidence handling

Acceptance: fake-provider E2E run produces three ranked, evidence-linked ideas with complete prompts.

## Phase 5 — Artwork generation and approval

- [ ] OpenAI Image and Recraft adapters
- [ ] Queued generation jobs, retry/idempotency/cost capture
- [ ] Object storage and provenance
- [ ] Artwork comparison UI and approval gate

Acceptance: mocked E2E generates two alternatives; duplicate requests are billed once in the ledger.

## Phase 6 — Production pipeline

- [ ] Validation, alpha/background workflow, safe trim, upscale
- [ ] Deterministic typography
- [ ] Mockup templates
- [ ] PNG QA report and approval preview

Acceptance: fixture-based tests prove dimensions, alpha, margins, spelling, hashes, and malicious-input rejection.

## Phase 7 — SEO, legal review, and package

- [ ] Listing title, description, tags, AI disclosure
- [ ] Preliminary phrase-risk records and human acknowledgement
- [ ] Licence, instructions, manifest, ZIP
- [ ] Listing review UI with optimistic concurrency

Acceptance: package is reproducible and Etsy rules are configurable rather than scattered constants.

## Phase 8 — Etsy integration

- [ ] Seller App OAuth with PKCE/state
- [ ] Draft listing, image upload, and digital-file upload
- [ ] Rate-limit handling and resumable partial failure
- [ ] Final approval enforcement

Acceptance: staging/test flow creates one draft only, never activates it, and resumes safely after simulated failure.

## Phase 9 — Operations and production readiness

- [ ] Dashboards, alerts, backups, restore test
- [ ] Spend caps and monthly usage report
- [ ] Security review, dependency audit, retention controls
- [ ] Deployment and runbook

Acceptance: production checklist is signed off and rollback/restore are documented and tested.

## Phase 10 — Optional SaaS expansion

Do not begin until the private single-shop MVP has real usage evidence.

- [ ] Tenant isolation and team roles
- [ ] Etsy Personal/Commercial Access requirements
- [ ] Subscription billing and quotas
- [ ] Data export/deletion and support tooling
- [ ] Abuse prevention and public legal pages

