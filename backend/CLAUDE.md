# CLAUDE.md — FastAPI Service

These rules extend the root instructions for `backend`.

## Layering

```text
presentation/api/routes → application/use_cases → domain
                                         ↓
                                  ports/interfaces
                                         ↑
                                 infrastructure adapters
```

- Routes parse/authenticate/authorize, call one use case, and map the result.
- Use cases own orchestration and transaction boundaries.
- Domain owns invariants and state transitions.
- Repositories hide SQLAlchemy details.
- Provider adapters live outside the domain.

## FastAPI rules

- Use async request handling. Do not block the event loop with image or archive work.
- Dependency injection wires repositories, services, auth, and settings.
- Pydantic request/response models are distinct from ORM and domain entities.
- Never expose encrypted tokens, storage keys, internal exceptions, or raw provider payloads.
- Add request IDs and correlation IDs to responses and logs.
- Use explicit response models and status codes.

## Data and migrations

- SQLAlchemy 2 typed mappings.
- Alembic migration for every schema change.
- Constraints enforce unique idempotency keys, one decision per immutable target version, and valid status values.
- Use row locking or compare-and-set for workflow transitions.
- Migrations must be reversible when practical and tested against a fresh database.

## Provider boundaries

Define protocols for:

- `ResearchProvider`
- `TextGenerationProvider`
- `ImageGenerationProvider`
- `ImageProcessingProvider`
- `ObjectStorage`
- `EtsyGateway`
- `TrademarkDataGateway`
- `CostCalculator`

Each adapter normalizes provider errors into retryable, rate-limited, authentication, invalid-request, budget, and permanent categories.

## Etsy integration

- OAuth authorization code flow with PKCE and state.
- Encrypt tokens and rotate refresh tokens safely.
- Respect QPS/QPD headers, `retry-after`, and cache rules.
- Create drafts only after final local validation and approval.
- Upload images and digital files idempotently; persist Etsy IDs after each step.
- Partial failure must resume without duplicating uploads or listings.
- Never scrape Etsy or sidestep the API.

## Tests

- Pytest unit and integration suites.
- HTTP adapter tests use mocked transports and sanitized fixtures.
- OAuth tests cover invalid state, expiry, refresh, scope rejection, and revoked access.
- State-transition tests cover stale versions and repeated requests.

