# ADR-0002 — Single-owner authentication with Argon2id and session cookies

- **Status**: Accepted (implementation in Phase 3)
- **Date**: 2026-08-01
- **Phase**: 1

## Context

The MVP has exactly one authenticated owner and one Etsy shop. Multi-tenant
support is explicitly out of scope until Phase 10, and only after the private
tool has real usage evidence.

Authentication is still required outside local development. The application
holds Etsy OAuth tokens and can spend money, so an unauthenticated instance is
not acceptable even for a single user.

## Decision

Use **local single-owner authentication**: one owner record, a password hashed
with **Argon2id**, and a server-side session in an `HttpOnly`, `Secure`,
`SameSite=Lax` cookie. Mutation routes are CSRF-protected. Implementation lands
in Phase 3.

A trusted OIDC provider remains a supported alternative behind the same port, so
the choice can change without touching use cases.

## Why

- **One user does not justify an identity provider.** Adding OIDC now means an
  external dependency, a redirect flow and provider configuration for a login
  that exactly one person performs.
- **Argon2id** is the current recommendation for password hashing and resists
  GPU attack far better than PBKDF2 or bcrypt at comparable cost settings.
- **Cookies over bearer tokens in the browser.** An `HttpOnly` cookie is not
  readable by script, which removes the most common token-exfiltration path. The
  cost is CSRF protection, which is a well-understood, local problem.
- **Sessions are revocable.** A stateless JWT would be simpler to issue and
  harder to revoke; for a tool holding OAuth tokens, revocation matters more.

## Consequences

- The API needs session storage and a CSRF token mechanism on mutating routes.
- Etsy OAuth refresh and access tokens are encrypted at rest with a versioned
  application key (`ENCRYPTION_KEY` + `ENCRYPTION_KEY_VERSION`), so the key can
  be rotated without a migration that decrypts everything at once.
- Tokens, hashes and keys are never returned by an API response and never
  logged; the redaction processor in `app/infrastructure/logging.py` enforces
  the second half of that.
- Phase 10 SaaS expansion will need tenant scoping added to every query. That is
  a known, deliberate debt, not an oversight.

## Alternatives considered

- **OIDC from the start** — better if this ever becomes multi-user, but an
  external dependency for a single-owner tool that must run locally.
- **Stateless JWT** — easy to issue, hard to revoke.
- **HTTP Basic auth behind a proxy** — no session control, no CSRF story, and
  credentials on every request.
