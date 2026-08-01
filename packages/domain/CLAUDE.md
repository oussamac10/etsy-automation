# CLAUDE.md — Domain Package

These rules extend the root instructions for `packages/domain`.

## Purity

- No framework, database, HTTP, queue, filesystem, environment, or provider SDK imports.
- Domain code is deterministic except through injected clock/ID services.
- Entities protect their own invariants; callers cannot assign arbitrary workflow states.
- Use explicit value objects for money, score, dimensions, tags, phrase, hash, provider model, and workflow status.

## Invariants

- An artwork job cannot start without an approved immutable idea version.
- Production cannot start without an approved immutable artwork asset.
- Etsy draft creation cannot start without completed QA, package, IP acknowledgement, and final listing approval.
- An approval refers to a version/hash, not only an entity ID.
- Tags are unique after normalization and respect current configured Etsy limits.
- The cost ledger uses integer minor currency units or Decimal, never float.
- Total run cost is derived from immutable usage entries.
- Evidence observation and inference are distinct fields.
- Risk is `low`, `medium`, `high`, or `unknown`; `safe` is not a valid value.

## Testing

Use table-driven tests for every transition and invariant. Property-test scoring bounds, money addition, tag normalization, and idempotency-key stability where useful.

