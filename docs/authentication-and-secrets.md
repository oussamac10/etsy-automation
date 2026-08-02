# Authentication and secrets

How the application proves who you are, keeps one owner's data away from
another's, and stores provider credentials. Implements ADR-0002; delivered in
Phase 3.

The short version: passwords are Argon2id hashes, sessions are rows in the
database referenced by a cookie holding a token the database never sees in the
clear, ownership always comes from the session, and provider secrets are Fernet
ciphertext that no endpoint can read back.

## Authentication

### Accounts

There is no registration route. The MVP has one owner, created by an operator:

```bash
BOOTSTRAP_OWNER_EMAIL=me@example.com \
BOOTSTRAP_OWNER_PASSWORD='...' \
python -m app.fixtures.bootstrap_owner
```

The password is read from the environment, never echoed, never logged and never
written to a file. Re-running leaves an existing account untouched — including
its password — so the command cannot be used to take an account over.

Development additionally seeds two fake owners (`dev-owner@example.invalid` and
`dev-second-owner@example.invalid`) with a placeholder password, so ownership
isolation can be exercised locally and in tests. Both addresses use `.invalid`,
which can never be a real domain.

### Passwords

`argon2-cffi` with Argon2id at the library's current defaults
(`app/infrastructure/security.py`). No password is stored, and no reversible
representation of one exists anywhere in the system.

- `verify_password` returns `False` for a missing or corrupt hash instead of
  raising, so a malformed row is a failed login, not a 500.
- A user with `password_hash IS NULL` — for example a Phase 2 fixture row —
  cannot authenticate at all.
- `needs_rehash` is available for when parameters are raised later.

### Sessions

Server-side, per ADR-0002. On login:

1. A 256-bit URL-safe token is generated with `secrets`.
2. Only its SHA-256 hash is stored, in `user_sessions.token_hash` (unique).
3. The token goes to the browser in an `HttpOnly`, `SameSite=Lax` cookie
   (`SESSION_COOKIE_NAME`, default `etsy_session`), `Secure` outside
   `APP_ENV=local` — startup refuses to run otherwise.
4. A separate CSRF token goes out in a readable cookie.

The token is never in a response body, a log line or a database column. A stolen
database gives an attacker hashes, not sessions.

Expiry is `SESSION_TTL_HOURS` (default 12, max 720). A session is valid only
while `revoked_at IS NULL AND expires_at > now`. Logout revokes rather than
deletes, so the row remains as evidence. Deactivating a user ends every session
immediately, because the session lookup re-checks `is_active` on each request.

### CSRF

Double-submit, compared against the session row rather than only against the
cookie: the client copies the CSRF cookie into `X-CSRF-Token`, and the value
must equal the token stored on the session. A cookie-only comparison would
accept a value an attacker planted in both places.

Applied to `POST`, `PUT`, `PATCH` and `DELETE`. Safe methods do not need it.
Order matters: authentication is checked first, so a request with no session
hears "log in", not "your CSRF token is wrong".

### Error responses

Every failure to authenticate answers the same way — `401` with type
`/problems/invalid-credentials` and the message "Email or password is
incorrect." — whether the account does not exist, the password is wrong or the
account is disabled. Nothing distinguishes them, including response timing
beyond what Argon2 itself imposes.

### Endpoints

| Method | Path                 | Auth | Notes                             |
| ------ | -------------------- | ---- | --------------------------------- |
| POST   | `/api/v1/auth/login` | no   | Sets both cookies                 |
| POST   | `/api/v1/auth/logout`| no   | Idempotent; safe without a session |
| GET    | `/api/v1/auth/me`    | yes  | Current owner; never a hash        |

Everything under `/api/v1/settings` and `/api/v1/workflows` requires a session.
`/api/health`, `/api/health/live` and `/api/v1/workflow` (the static pipeline
description) stay public: they expose no owner data.

## Ownership

**The owner is always the authenticated user.** No use case in
`app/application/` accepts an owner ID from a request body, and the workflow
create schema rejects an `owner_id` field outright (`422`), so a client cannot
propose one. This is why cross-owner access is not a check that can be forgotten
at a route: there is no code path where a client-supplied identity reaches a
query.

### Cross-owner access answers 404, not 403

Asking for another owner's workflow — or its timeline, ideas or approvals —
returns exactly the same `404` as asking for a UUID that does not exist. A `403`
would confirm the resource is real, which is an enumeration oracle. The
integration suite asserts the two responses are byte-identical once the
per-request `correlation_id` and `instance` are stripped.

The rule applies to nested resources as well: the parent workflow is resolved
under the owner filter first, so a nested route cannot become a side door.

Settings and credentials are keyed by user ID, so isolation there is structural:
one owner's `PATCH` cannot reach another's row, and deleting a credential that
belongs to someone else is a `404`.

## Provider credentials

### Storage

`provider_credentials` holds one row per (user, provider), enforced by a unique
constraint, and has **no column that can hold plaintext**:

| Column         | Contents                                        |
| -------------- | ----------------------------------------------- |
| `ciphertext`   | Fernet token (`BYTEA`, non-empty)               |
| `key_version`  | Which application key produced it (`>= 1`)      |
| `masked_value` | `••••••••` plus the last four characters        |
| `label`        | The owner's own note, e.g. which account        |

Encryption is `cryptography`'s Fernet (AES-128-CBC + HMAC-SHA256), with the key
derived from `ENCRYPTION_KEY` by HKDF-SHA256. Nothing here is hand-rolled
cryptography. Deriving means the operator's key can be any string of at least 32
characters and still produce a valid 32-byte Fernet key, reproducibly across
restarts.

### Nothing decrypts through the API

There is no endpoint that returns a credential. `PUT` and `GET` return only the
metadata above; `store_credential` masks the plaintext and discards it. The one
function that decrypts, `reveal_credential`, is deliberately unreachable from
any route — it exists for the provider adapters that arrive in Phase 5.

Audit events record the provider and the mask, never the secret. The logging
redaction processor covers the rest.

### Missing or invalid encryption configuration

If `ENCRYPTION_KEY` is missing or too short, the cipher is not built and every
credential write answers `503` with `/problems/encryption-unavailable`. It never
falls back to storing plaintext, and no row is written. Reads of credential
*metadata* still work, because that data is not encrypted.

### Key rotation

The key can be replaced without losing a stored secret. Three steps, no
downtime:

```bash
# 1. New key current, old key retained, version bumped:
#      ENCRYPTION_KEY=<new>
#      ENCRYPTION_KEY_VERSION=2
#      ENCRYPTION_KEY_PREVIOUS=<old>
#      ENCRYPTION_KEY_PREVIOUS_VERSION=1
# 2. Re-encrypt every row still on the old key:
python -m app.rotate_encryption_key
# 3. Unset ENCRYPTION_KEY_PREVIOUS and ENCRYPTION_KEY_PREVIOUS_VERSION.
```

Between steps 1 and 3 both keys decrypt and writes use the new one. Step 2 is
re-runnable (a row already at the current version is skipped) and commits once,
so a failure part-way leaves nothing half-rotated. Running it without the
retired key configured refuses and changes nothing rather than destroying what
it cannot read.

Startup validation refuses half a rotation: the previous key and its version
must be set together, and the previous version must be lower than the current
one.

**Limitation:** exactly one retired key is held at a time. Finish a rotation
before starting the next. Ciphertext at any other version is reported as a
configuration error, not retried against every key in turn.

## What is never stored, logged or returned

- A password, in any reversible form.
- A session token — only its SHA-256 hash.
- A provider secret — only Fernet ciphertext and a four-character suffix.
- An encryption key, in the repository or in any response.

`ENCRYPTION_KEY`, `SECRET_KEY` and every credential come from environment
configuration. `.env` is git-ignored; `.env.example` holds placeholders that
startup validation rejects outside `APP_ENV=local`.

## Related

- `docs/adr/0002-single-owner-authentication.md` — the decision and its
  alternatives
- `docs/progress/phase-3-auth-settings.md` — what Phase 3 delivered and verified
- `apps/api/src/app/infrastructure/security.py` — hashing, tokens, cipher, mask
