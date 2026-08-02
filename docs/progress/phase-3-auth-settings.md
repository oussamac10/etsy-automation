# Phase 3 — Authentication and Settings

**Status:** Complete
**Date:** 2026-08-02
**Branch:** `feature/phase-3-auth-settings`
**Next phase:** Phase 4 — Telegram remote control (not started)

## Acceptance criteria

> Unauthorized access is rejected, sensitive values never return through APIs,
> and encrypted secrets can be rotated without data loss.

Met. Evidence below.

---

## What was implemented

Three concerns, one phase: who you are, what is yours, and where secrets live.
The design rationale is in
[`docs/authentication-and-secrets.md`](../authentication-and-secrets.md); this
document records what was built and what was verified.

### Authentication (ADR-0002, now implemented)

| Module | Contents |
|---|---|
| `infrastructure/security.py` | Argon2id hashing, session token generation and hashing, constant-time comparison, `CredentialCipher`, `mask_secret` |
| `application/auth.py` | `create_owner`, `authenticate`, `resolve_session`, `end_session` — the use cases that own the transaction |
| `api/dependencies.py` | `get_current_user` (session cookie → user, CSRF on mutations), `build_credential_cipher` |
| `api/routes/auth.py` | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` and the cookie handling |
| `fixtures/bootstrap_owner.py` | Operator command to provision the single owner |

- **Passwords**: Argon2id via `argon2-cffi` (new dependency; the algorithm
  ADR-0002 chose has no standard-library implementation). No password and no
  reversible form of one is stored.
- **Sessions**: server-side rows. The 256-bit token goes to the browser in an
  `HttpOnly`, `SameSite=Lax` cookie; only its SHA-256 hash is stored. `Secure` is
  forced outside `APP_ENV=local` by startup validation.
- **CSRF**: double-submit compared against the session row, on every unsafe
  method. A cookie-only comparison would accept a planted value.
- **Generic failures**: wrong password, unknown account and disabled account are
  indistinguishable — the same `401` and the same message.
- **No registration route**, per the roadmap. The owner is provisioned with
  `python -m app.fixtures.bootstrap_owner`, reading the password from the
  environment. No real password is committed anywhere.

### Ownership enforcement

Every `/api/v1/workflows` and `/api/v1/settings` route now requires a session,
and **the owner is always the authenticated user**. `WorkflowCreateRequest`
forbids extra fields, so a client-supplied `owner_id` is a `422` rather than a
silently honoured claim; no use case takes an owner ID a client can influence.

Cross-owner access — a workflow, its timeline, its ideas or its approvals —
answers `404`, byte-identical to a nonexistent ID once the per-request
`correlation_id` and `instance` are removed. A `403` would confirm the resource
exists.

One related tightening: `GateDecisionRequest` no longer accepts `actor`. An
approval is the evidence that a human decided, so the name recorded comes from
the session, not the request body.

### Settings

`owner_settings`, one row per owner, created on first read rather than at signup
so an account created by a fixture or a migration cannot end up without one.

| Group | Fields |
|---|---|
| Target market | `target_marketplace`, `target_country`, `currency`, `default_language` |
| Idea/research | `default_idea_mode`, `default_target_buyer`, `default_product_uses` |
| Style | `style_preferences` (≤ 20, trimmed and deduped), `style_notes`, `avoid_terms` |
| Quality | `default_quality_tier`, `min_output_pixels`, `require_transparent_background` |
| Budgets | `daily_budget_minor`, `monthly_budget_minor` (`BIGINT` minor units) |
| Schedule/notifications | `weekly_research_enabled`, weekday, hour, three notification flags |

Validation happens at the API boundary (`UpdateSettingsRequest`, `extra="forbid"`,
partial updates via `exclude_unset`) *and* in the database — nine `CHECK`
constraints, including `daily_budget_minor <= monthly_budget_minor`. Money is
`Decimal` with exactly two places in, integer minor units at rest; a third
decimal place is a `422` because it has nowhere to go.

### Provider credentials

`provider_credentials`, one row per `(user_id, provider)`, with **no column that
can hold plaintext**: Fernet ciphertext, the key version that produced it, a
masked suffix and an optional label.

- Encryption is `cryptography`'s Fernet with the key derived from
  `ENCRYPTION_KEY` by HKDF-SHA256. Nothing is hand-rolled.
- No endpoint decrypts. `reveal_credential` exists for the Phase 5 adapters and
  is wired to no route.
- Replacing overwrites in place, so a stale secret cannot linger beside its
  replacement.
- A missing or invalid key produces `503 /problems/encryption-unavailable` and
  writes nothing. There is no plaintext fallback.

**Key rotation** (the acceptance criterion): `ENCRYPTION_KEY_PREVIOUS` plus
`ENCRYPTION_KEY_PREVIOUS_VERSION` keep the retired key readable while
`python -m app.rotate_encryption_key` re-encrypts each row under the new key.
Re-runnable, commits once, and refuses rather than destroys when the retired key
is absent. Startup rejects half a rotation. One retired key is held at a time.

## Database and migration

Migration `0003_phase_3_auth_settings` (`down_revision = 0002_phase_2_domain`):

- `users.password_hash` added (`TEXT`, nullable — a Phase 2 row cannot sign in).
- `user_sessions`: unique `token_hash`, `CHECK expires_at > created_at`,
  `ON DELETE CASCADE`, two indexes.
- `owner_settings`: unique `user_id`, nine `CHECK` constraints.
- `provider_credentials`: unique `(user_id, provider)`, `key_version >= 1`,
  non-empty ciphertext, index on `user_id`.
- New enum type `quality_tier`; six values appended to `audit_action` with
  `ALTER TYPE ... ADD VALUE IF NOT EXISTS`, so a downgrade→upgrade cycle repeats
  cleanly even though PostgreSQL has no `DROP VALUE`.

`downgrade()` drops the three tables, the column and `quality_tier`, and
documents why the enum values stay. No existing migration was edited.

Phase 1 and Phase 2 tables are untouched. 21 tables total.

## API endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/auth/login` | no |
| POST | `/api/v1/auth/logout` | no (idempotent) |
| GET | `/api/v1/auth/me` | yes |
| GET / PATCH | `/api/v1/settings` | yes |
| GET | `/api/v1/settings/credentials` | yes |
| PUT / DELETE | `/api/v1/settings/credentials/{provider}` | yes |

`/api/v1/workflows*` became authenticated. `/api/health`, `/api/health/live` and
`/api/v1/workflow` (the static pipeline description) remain public; they expose
no owner data, and the web app depends on them.

Errors stay RFC 9457. New types: `/problems/invalid-credentials` (401),
`/problems/not-authenticated` (401), `/problems/csrf-failed` (403),
`/problems/encryption-unavailable` (503), `/problems/invalid-budget-relation`
(422).

## Frontend

**Deferred, deliberately.** `docs/PHASES.md` gives Phase 3 no frontend bullet,
and the web app calls no protected endpoint today — only `/api/health` and the
static `/api/v1/workflow`, both still public, both still passing their tests and
the 11 end-to-end checks. Login, logout and settings screens land with the
dashboard in Phase 5 rather than being invented ahead of the screens they belong
to. This is recorded in `docs/PHASES.md` and `TODO.md`.

No frontend file was changed in this phase.

## Development data

`app/fixtures/dev_seed.py` now seeds **two** owners
(`dev-owner@example.invalid`, `dev-second-owner@example.invalid`), the second
with a workflow of its own, so ownership isolation is demonstrable locally and
assertable in tests. Both use a clearly fake `.invalid` domain and a placeholder
password. No provider credential is seeded — asserted by a test. Re-running is
idempotent.

## Security decisions

1. **404, not 403, across owners.** Anti-enumeration; asserted byte-for-byte.
2. **Session rows, not JWTs.** Revocation matters more than statelessness for a
   tool that will hold OAuth tokens. Deactivating a user ends every session at
   once.
3. **CSRF token compared against the session row**, not just the cookie.
4. **The owner is never an input.** Ownership cannot be forgotten at a route
   because there is no path for a client identity to reach a query.
5. **The credential table has no plaintext column.** Not a policy — a schema.
6. **Fail closed on missing encryption.** `503`, no write, no fallback.
7. **The approval actor comes from the session.** Gate evidence a client can
   name is not evidence.

## Tests

All new, none weakened or removed. Phase 1 and Phase 2 suites are intact.

| Suite | Tests | Covers |
|---|---|---|
| `tests/test_security.py` | 26 | Argon2 hashing and verification, session tokens, Fernet round-trip and failures, retired-key rotation, masking |
| `tests/test_settings_schemas.py` | 19 | Boundary validation, partial updates, currency/marketplace/country, budget precision, collections, secrets unprintable from request models |
| `tests/test_settings.py` | 17 | Environment validation including key length, cookie security and rotation pairing |
| `tests/integration/test_api_auth.py` | 31 | Login, generic failures, cookie flags, `/me`, forged/expired/revoked sessions, CSRF, logout, hash-only storage, audit trail |
| `tests/integration/test_api_settings.py` | 33 | Defaults, partial updates, budget precision and relation, validation, isolation, credential store/mask/replace/delete, ciphertext at rest, missing-key `503`, audit events |
| `tests/integration/test_auth_repositories.py` | 25 | Session/settings/credential repositories, every new `CHECK` and unique constraint, cascade deletes, key rotation end to end |
| `tests/integration/test_api_workflows.py` | 34 | Now under a session: owner from the session, client `owner_id` refused, cross-owner isolation on every nested route |
| `tests/integration/test_fixtures.py` | 19 | Two owners, hashed passwords, disjoint workflows, no seeded credential |

Provider calls remain disabled; nothing in this phase contacts an external API.

## Verification

Every check below was run. Commands are reproducible from the repository root
unless noted.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Clean migration upgrade | `alembic upgrade head` on a fresh `etsy_fresh` database | Pass — `0001 → 0002 → 0003` |
| 2 | Downgrade then upgrade | `alembic downgrade base && alembic upgrade head` | Pass |
| 3 | Backend unit tests | `pytest --ignore=tests/integration` (apps/api) | **233 passed** |
| 4 | Backend integration tests | `pytest tests/integration` with `TEST_DATABASE_URL` | **186 passed** |
| 5 | Ruff lint | `ruff check` (api + worker) | Pass |
| 6 | Ruff format | `ruff format --check` | Pass |
| 7 | mypy strict | `mypy .` (api + worker) | Pass — 92 + 8 files |
| 8 | Frontend tests | `pnpm test` | **67 passed** (22 + 8 + 17 + 20) |
| 9 | Frontend lint | `pnpm lint` | Pass |
| 10 | Frontend typecheck | `pnpm typecheck` | Pass |
| 11 | Image worker | included in 5–10 above | Pass — 17 tests |
| 12 | Compose config | `docker compose config -q` | Pass |
| 13 | Fixture loading | `python -m app.fixtures.dev_seed`, run twice | Pass — idempotent |
| 14 | End-to-end | `pnpm test:e2e` | **11 passed** |
| 15 | Worker tests | `pytest apps/worker` | **23 passed** |
| 16 | Secret and large-file review | diff read in full; `git status` reviewed | No secret, no binary |

Total: 419 Python API tests, 23 worker, 67 TypeScript unit, 11 end-to-end.

Notes on how checks were run:

- The local Compose stack publishes remapped host ports (PostgreSQL `55432`,
  Redis `56379`, API `8800`, web `3300`) because other containers hold the
  defaults. Integration tests therefore used
  `TEST_DATABASE_URL=postgresql+asyncpg://etsy:etsy_local_password@localhost:55432/etsy_test`
  and the end-to-end run used `E2E_WEB_URL`/`E2E_API_URL`. CI uses the default
  ports and needs no override.
- CI's `ENCRYPTION_KEY` was lengthened to satisfy the new 32-character minimum;
  without that change every CI job that builds `Settings` would fail.

## Known limitations

- **One retired encryption key at a time.** Finish a rotation before starting
  the next; ciphertext at any other version is a configuration error.
- **No frontend authentication UI** (see above).
- **No `ShopConnection` and no Telegram token row.** The cipher and the
  key-version column are ready; the tables belong to the phases that own the
  flows (9 and 4).
- **Sessions are not swept.** Expired rows stay until something deletes them.
  They are inert — expiry is checked on every lookup — but a periodic clean-up
  belongs with the scheduler in Phase 10.
- **One owner.** Nothing here adds tenancy; Phase 11 would still need scoping on
  every query, as ADR-0002 records.
- **No rate limiting on login.** Argon2 makes online guessing slow, but a real
  limiter belongs with deployment (Phase 10).

## Cost impact

None. No paid provider is called, no adapter was added, and `PROVIDER_MODE=live`
is still refused at startup. The budget *settings* added here are configuration;
enforcement against real spend arrives with the providers.

## Recommended Phase 4 starting point

Phase 4 is Telegram remote control. Start with the webhook: a private adapter
behind a secret path, verifying Telegram's webhook secret and an owner-ID
allow-list before anything else, then idempotent callback handling. The
authentication in this phase does not apply to Telegram — the bot is a second
identity channel for the same single owner — so the first design decision is how
a Telegram sender maps to the owner record.

The encrypted-credential table is the right home for the bot token; adding
`telegram` to `ProviderName` and reusing `store_credential` avoids a second
secret mechanism.
