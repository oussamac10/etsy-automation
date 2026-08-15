# CLAUDE.md — Test Suites

These rules extend the root instructions for `tests`.

## Test pyramid

- Many fast domain/unit tests
- Focused adapter contract tests
- Database/queue/storage integration tests
- A small number of critical Playwright end-to-end tests
- Explicit manual paid-provider smoke tests outside normal CI

## Required scenarios

1. Research run produces evidence, keyword clusters, scored ideas, and prompts.
2. Low-confidence research is visibly labeled.
3. Rejected idea cannot generate artwork.
4. Duplicate artwork request costs money once.
5. Rejected artwork cannot enter production.
6. Failed background removal can retry without losing the master.
7. Exact slogan spelling is rendered by the deterministic typography pipeline.
8. IP acknowledgement is required.
9. Stale listing approval is rejected after edits.
10. Etsy partial upload resumes without a duplicate listing.
11. Budget ceiling blocks a paid call.
12. Secrets are redacted from logs and API responses.

## Fixture rules

- No real user tokens, shop data, seller content, or copyrighted artwork.
- Provider fixtures are minimal, sanitized, and versioned.
- Generated image fixtures are original simple geometric samples.
- Freeze time and random seeds when determinism matters.
