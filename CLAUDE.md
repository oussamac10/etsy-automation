# CLAUDE.md — Etsy PNG Automation

## Mission

Build a production-minded application that helps one Etsy seller research original PNG product ideas, approve a concept, generate artwork alternatives, approve one artwork, process and package the files, generate listing SEO, perform a preliminary IP-risk review, and create an Etsy draft.

The app automates preparation. It does not promise sales, certify legal safety, or publish unchecked products.

## Required workflow

The state machine is authoritative:

```text
RESEARCHING
→ IDEA_REVIEW
→ ART_GENERATION
→ ART_REVIEW
→ PRODUCTION
→ IP_REVIEW
→ LISTING_REVIEW
→ ETSY_DRAFT_CREATED
```

Failure states must be explicit and retryable. Never skip these three human gates:

1. Idea approval
2. Artwork approval
3. IP acknowledgement and final listing approval

Never automatically publish or activate an Etsy listing.

## MVP stack

- Monorepo: pnpm workspaces for frontend/shared TypeScript; Python service managed independently.
- Frontend: Nuxt 3, Vue 3, TypeScript, Pinia, Tailwind.
- API: FastAPI, Python 3.12+, SQLAlchemy 2, Alembic, Pydantic 2.
- Database: PostgreSQL 16.
- Queue: Redis plus Dramatiq or Celery. Choose one in Phase 1 and document the decision.
- Image processing: Node.js TypeScript service using Sharp and SVG templates.
- Object storage: S3-compatible adapter; MinIO locally.
- Providers: OpenAI, Recraft, Etsy Open API v3, optional USPTO TSDR data adapter.
- Local development: Docker Compose.

Do not add n8n to the MVP. The application itself owns orchestration, idempotency, audit history, and approval gates.

## Product scope

### Included

- Single authenticated owner and one Etsy shop
- Manual `Run research` action and optional weekly schedule
- Country, language, season, audience, style, and product-use brief
- At least three buyer-intent query angles per research run
- Evidence records with URL, title, observed fact, timestamp, and source type
- Keyword clusters, competition signals, risk notes, scoring, and ranked ideas
- A complete design prompt and negative prompt for every idea
- OpenAI and Recraft provider adapters
- Artwork comparison and manual selection
- Background removal, edge checks, dimensions, upscaling, typography overlay, and mockups
- Listing title, description, exactly 13 or fewer valid tags, AI disclosure, licence, instructions, and ZIP
- Preliminary phrase/IP-risk workflow with mandatory human acknowledgement
- Etsy OAuth and draft listing creation
- Cost ledger and per-run budget limits
- Audit log for provider calls, approvals, retries, and external IDs

### Excluded from MVP

- Automatic Etsy publishing
- Claims that an idea is profitable, safe, or trademark-free
- Screen-scraping Etsy or bypassing API access rules
- Canva browser automation
- Multi-tenant billing or subscriptions
- Autonomous legal conclusions
- Copying seller titles, artwork, brands, characters, celebrities, lyrics, or recognizable styles

## Etsy research rules

Implement the research module as provider interfaces, not hard-coded scraping.

For every research run:

1. Save the brief: marketplace, country, language, buyer, physical uses, style, quantity, and season.
2. Run broad, long-tail, occasion/recipient, style, and use-case queries. Use at least three distinct angles.
3. Store evidence and distinguish observation from inference.
4. Build natural keyword clusters: primary phrase, attributes, recipient/occasion, and use cases.
5. Generate original concepts using a real differentiator.
6. Generate a self-contained design prompt and separate negative prompt for every concept.
7. Score each idea from 1–5 on demand signal, competition opportunity, seasonal timing, buyer clarity, differentiation, product versatility, and IP risk.
8. Use weighted score:

```text
0.20 demand
+ 0.15 competition opportunity
+ 0.15 seasonal timing
+ 0.15 buyer clarity
+ 0.15 differentiation
+ 0.10 product versatility
+ 0.10 IP safety
```

If reliable evidence is thin, label confidence low and propose a test. Never invent search volume, sales, conversion, or revenue.

## Design prompt contract

Every prompt must specify:

- subject and supporting elements
- composition and hierarchy
- visual style without naming a living artist or copying a seller
- palette
- outlines, detail, and texture
- intended products
- isolated artwork and clean uncropped edges
- high-resolution print intent
- no typography when exact spelling matters

Store the exact phrase separately with font, layout, color, and placement instructions. The negative prompt must reject backgrounds, mockups, garments, models, watermarks, signatures, trademarks, copyrighted characters, copied styles, artifacts, malformed anatomy, illegible text, and cropped objects.

Do not claim that generation guarantees transparency, exact pixel dimensions, DPI, or spelling. Validate outputs afterward.

## Core domain model

Use UUID primary keys and UTC timestamps.

- `User`: owner identity and settings
- `ShopConnection`: encrypted Etsy tokens, scopes, expiry, shop ID
- `ResearchRun`: brief, status, budget, total cost, confidence
- `ResearchEvidence`: query, URL, title, observation, source, captured_at
- `KeywordCluster`: primary and secondary phrases
- `ProductIdea`: concept, buyer intent, differentiation, season, score breakdown, risk
- `DesignPrompt`: positive prompt, negative prompt, phrase, typography instructions, version
- `ArtworkJob`: provider, model, parameters, idempotency key, status, cost, external ID
- `Asset`: storage key, SHA-256, MIME type, dimensions, alpha status, provenance
- `Approval`: gate, actor, decision, note, timestamp, immutable target version
- `ProductionJob`: chosen asset, operations, status, QA result
- `Mockup`: template, output asset
- `IpReview`: phrase, preliminary results, risk flags, human acknowledgement
- `ListingDraft`: title, description, tags, price, taxonomy, state, Etsy listing ID
- `Package`: PNG, licence, instructions, ZIP manifest
- `ProviderUsage`: provider, operation, units, currency, estimated and actual cost
- `AuditEvent`: actor, action, entity, before/after metadata, correlation ID

Never delete audit, approval, cost, or provenance records through normal application flows.

## Architectural rules

- Keep domain logic independent of FastAPI, Nuxt, provider SDKs, and storage.
- Define ports/interfaces for search, text AI, image generation, image processing, storage, Etsy, IP data, clock, and cost calculation.
- Provider responses are untrusted input. Validate before persistence.
- Every slow or paid operation runs as a queued job.
- Every paid/external job has an idempotency key, retry policy, timeout, and cost ceiling.
- Retries use exponential backoff with jitter and do not retry permanent 4xx errors.
- Persist job state before and after an external call.
- Never hold a database transaction open during a network request.
- Use an outbox pattern for important job dispatch and integration events.
- Store binary assets in object storage, never PostgreSQL.
- Store content hashes to detect duplicates.
- Configuration comes from environment variables validated at startup.
- Secrets are never logged, returned to the browser, committed, or embedded in ZIP files.

## API conventions

- Prefix routes with `/api/v1`.
- Return RFC 9457-style problem details for errors.
- Use cursor pagination for growing collections.
- Require optimistic concurrency/version fields for user-edited drafts.
- Accept `Idempotency-Key` for state-changing paid operations.
- Return `202 Accepted` plus a job resource for asynchronous actions.
- Expose job progress through polling first; WebSocket/SSE is optional after MVP.
- Generate and commit OpenAPI; generate frontend types from it.

Minimum endpoint groups:

```text
/auth
/settings
/research-runs
/ideas
/artwork-jobs
/assets
/approvals
/production-jobs
/ip-reviews
/listing-drafts
/etsy/oauth
/etsy/drafts
/usage
/jobs
```

## Security and compliance

- Single-owner authentication is still required outside local development.
- Hash passwords with Argon2id or use a trusted OIDC provider.
- Encrypt OAuth refresh/access tokens at rest with a versioned application key.
- Use least-privilege Etsy scopes and PKCE/state validation.
- Protect mutation routes against CSRF if cookie auth is used.
- Validate uploads by signature, MIME, size, pixel count, and decompression limits.
- Render SVG only through a hardened pipeline; reject scripts, external URLs, and active content.
- Prevent ZIP slip and path traversal.
- Use signed, short-lived asset URLs.
- Add rate limits and per-run spending limits.
- Redact prompts only when necessary; never redact provenance or cost records.
- Include the required Etsy API non-endorsement notice before any commercial release.

## Cost controls

Read `docs/API_COSTS.md` before implementing a paid provider.

- Centralize current prices in versioned configuration with `effective_from` and source URL.
- Calculate an estimate before dispatch.
- Reject jobs that exceed the run or monthly budget until the owner approves an override.
- Record model, size, quality, token counts, API units, estimated cost, actual cost, currency, and timestamp.
- Drafts use economical models and settings. Final generation uses the selected quality explicitly.
- Never silently fall back to a more expensive model.

## Code quality

- TypeScript strict mode; no unexplained `any`.
- Python fully typed; mypy strict for application modules.
- Small modules, explicit names, dependency injection at boundaries.
- No business logic in Vue components, route handlers, ORM models, or queue tasks.
- No provider SDK types in the domain layer.
- Use structured logging with correlation IDs; do not log secrets or raw binary data.
- Add docstrings/comments for decisions and invariants, not obvious syntax.
- Do not add dependencies without explaining the need in the commit/handoff.

## Test requirements

- Unit tests for scoring, state transitions, cost calculations, prompt contracts, tag validation, and ZIP manifest.
- Contract tests for every provider adapter using recorded sanitized fixtures or mocked HTTP.
- Integration tests with PostgreSQL, Redis, MinIO, and the worker.
- End-to-end tests for the happy path and rejected approvals.
- Provider calls are disabled in normal tests.
- A paid smoke test must require an explicit environment flag and budget.
- Tests must verify idempotency and duplicate delivery behavior.
- Image QA tests use deterministic fixtures, not subjective AI output assertions.

## Required commands

Once Phase 1 establishes exact scripts, keep this section synchronized. Expected command families:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
python -m ruff check .
python -m mypy .
python -m pytest
docker compose config
```

## Frontend work

For every task affecting `frontend`, load and follow the official
`frontend-design` skill.

Also follow these project requirements:

- Preserve routes, API contracts, validation and existing behavior.
- Reuse existing components and design tokens.
- Keep API and domain logic outside presentation components.
- Design mobile-first and meet WCAG AA accessibility.
- Respect reduced-motion preferences.
- Run frontend linting, type checking and relevant tests.
- Verify phone, tablet and desktop layouts.

## Claude working protocol

Before editing:

1. Read this file, the nearest nested `CLAUDE.md`, and `docs/PHASES.md`.
2. Inspect repository status and existing work.
3. State the active phase and acceptance criteria.
4. Do not repeat completed phases.

While editing:

- Work on one phase at a time unless the user explicitly expands scope.
- Make the smallest coherent change.
- Preserve user changes and unrelated work.
- Add migrations for schema changes.
- Update tests with behavior changes.
- Never call paid or write-capable external APIs without explicit test configuration.
- Never create or publish a real Etsy listing during automated tests.

Before stopping:

1. Run targeted tests, then the relevant full suite.
2. Review the diff for secrets, accidental generated binaries, and unrelated changes.
3. Update the checklist in `docs/PHASES.md` with evidence.
4. Report: completed work, files changed, tests run, known limitations, cost-impact changes, and exact next step.
5. Stop at the phase boundary.
