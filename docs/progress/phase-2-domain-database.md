# Phase 2 — Domain and Database

**Status:** Complete
**Date:** 2026-08-02
**Branch:** `feature/phase-2-domain-database`
**Next phase:** Phase 3 — Authentication and settings (not started)

## Acceptance criteria

> Every gate/state invariant and cost calculation is tested; every research run
> records its input mode; a supplied idea can be retrieved exactly as entered
> after an optimized version is created.

Met. Evidence below.

---

## What was implemented

### Domain layer (pure, no framework imports)

| Module | Contents |
| --- | --- |
| `domain/workflow.py` | The state machine, extended from 8 to 16 states with an explicit transition table, three gates, rejection/revision routing, per-stage failure states and the stage guards |
| `domain/enums.py` | `IdeaMode`, `ConceptOrigin`, `SourceType`, `SignalStrength`, `CompetitionLevel`, `Seasonality`, `ConfidenceLevel`, `ConceptStatus`, `ProviderName`, `CostStatus`, `AuditAction`, `ProductUse` |
| `domain/money.py` | `Money` — integer minor units, `Decimal` at the boundaries, never a float |
| `domain/ideas.py` | Idea-mode rules, origin validation, normalisation and `is_faithful_to_original` |
| `domain/errors.py` | `DomainError` and its subclasses, each mapped to an HTTP status |

### Persistence — 18 tables

`users`, `product_workflows`, `workflow_transitions`, `original_ideas`,
`original_idea_revisions`, `research_runs`, `research_evidence`,
`keyword_clusters`, `product_concepts`, `design_prompts`, `artwork_jobs`,
`assets`, `approvals`, `production_jobs`, `listing_drafts`, `provider_usage`,
`audit_events`, `workflow_failures`.

Full detail, including the ER diagram and the required-area → entity mapping, is
in [`docs/domain-model.md`](../domain-model.md).

### Repositories

Protocols in `ports/repositories.py`; SQL implementations in
`infrastructure/repositories/`. `UnitOfWork` gives one session and one
transaction per use case.

### Application and API

Use cases for create workflow, submit idea, revise idea, transition, decide gate,
list, get and timeline. Six endpoints:

```text
POST   /api/v1/workflows
GET    /api/v1/workflows
GET    /api/v1/workflows/{id}
POST   /api/v1/workflows/{id}/ideas
GET    /api/v1/workflows/{id}/ideas
GET    /api/v1/workflows/{id}/timeline
POST   /api/v1/workflows/{id}/approvals
```

### Fixtures

`app/fixtures/dev_seed.py` — three workflows, one per idea mode, with fixed UUIDs.

---

## Important architecture decisions

### 1. The Phase 1 state machine was extended, not duplicated

The brief's fifteen states map almost one-to-one onto Phase 1's eight. Rather
than build a parallel machine, `RunStatus` was extended: every Phase 1 name keeps
its meaning, and the new states (`DRAFT`, `RESEARCH_QUEUED`, `IDEA_APPROVED`,
`ART_QUEUED`, `ARTWORK_APPROVED`, `READY_FOR_ETSY_DRAFT`, `PUBLISHED`,
`CANCELLED`) name moments Phase 1 collapsed together.

Consequence for the Phase 1 tests. `test_workflow.py` went from 18 test
functions to 35. Five were **renamed** with the same guarantee intact
(`test_states_are_declared_in_workflow_order` → `test_happy_path_is_declared_in_order`,
`test_terminal_state_has_no_successor` → `test_terminal_states_have_no_exit`,
`test_advances_a_non_gated_state` → `test_advance_moves_a_non_gated_state`,
`test_approval_advances_the_run` → `test_approval_advances_the_workflow`,
`test_only_the_immediate_successor_is_allowed` → `test_each_happy_path_step_is_allowed`
plus `test_cannot_skip_a_state`).

Two were **replaced because the behaviour genuinely changed**, each by a stronger
assertion:

| Removed | Why | Replaced by |
| --- | --- | --- |
| `test_no_published_or_active_state_exists` | `PUBLISHED` now exists as a human-recorded state | `TestPublicationIsHumanOnly` — 3 tests asserting it is reachable only from `ETSY_DRAFT_CREATED`, that no gate targets it, and that gate 3 still guards the draft |
| `test_rejection_keeps_the_run_in_review` | A rejection now returns the workflow to the producing stage instead of parking it at the gate | `test_rejection_returns_to_the_producing_stage`, parametrised over all three gates and asserting the result is strictly earlier on the happy path |

`test_phase_1_state_names_are_preserved` was added to guard against a future
rename of the eight original states.

### 2. `PUBLISHED` is a record, not an action

The brief asked for a `Published` state; the root `CLAUDE.md` and Phase 9 both
forbid the application activating a listing. Both hold: `PUBLISHED` is reachable
only from `ETSY_DRAFT_CREATED`, no gate approval targets it, `EtsyGateway` still
has no publish method, and `is_terminal_success()` returns true for the draft
state only. The transition means "the owner published it themselves and told us".

### 3. The original idea is protected in three layers

Repository (no write method), attribute history (`guard_immutable` raises
`ImmutableFieldError`), and use case (a second submission is a 409 pointing at
the revision path). `normalized_text` is stored *beside* the original, never
instead of it.

### 4. Gate decisions leave a gated state through the gate, not around it

`advance()` refuses to leave a review state. A caller acting on a human decision
passes the gate and decision to `transition()`, which validates with
`apply_approval` instead. **This was found by a test**: the first implementation
made `decide_gate` impossible, because the repository refused the very move an
approval is supposed to cause.

### 5. `WorkflowError` inherits from `DomainError`

Also found by a test: gate errors were returning 500 instead of 409 because the
problem-details handler is registered for `DomainError` and `WorkflowError` was a
plain `Exception`.

### 6. Money is integer minor units everywhere

`BIGINT` columns, `Money` in Python, and a SQL mirror of `effective_cost_minor`
so the Python property and the aggregate query cannot drift.

### 7. No column can hold an invented market number

`ResearchEvidence` has no search-volume, sales or revenue column. Signals are
qualitative enums backed by the observation text.

---

## Migration

One revision: `0002_phase_2_domain`, on top of `0001_baseline`.

- 16 PostgreSQL enum types created once at the top of `upgrade()` (several tables
  share them), so every column uses `create_type=False`.
- 18 tables with foreign keys, unique constraints, check constraints and indexes.
- `downgrade()` drops the tables, then the enum types.

`alembic check` reports no drift between the models and the migration.

```text
alembic upgrade head      → 0001_baseline → 0002_phase_2_domain   ✅
alembic downgrade base    → 0002 → 0001 → base                    ✅
alembic upgrade head      → rebuilt cleanly                       ✅
```

The integration suite runs `downgrade base` then `upgrade head` on every session,
so a migration that only works on an empty database cannot pass unnoticed.

---

## Tests and results

All commands run on 2026-08-02.

| Suite | Command | Result |
| --- | --- | --- |
| API (unit + integration) | `pytest` | **261 passed** |
| Worker | `pytest` | **23 passed** |
| `@etsy/domain` | `vitest run` | **22 passed** |
| `@etsy/image-pipeline` | `vitest run` | **8 passed** |
| `@etsy/image-worker` | `vitest run` | **17 passed** |
| `@etsy/web` | `vitest run` | **20 passed** |

**351 tests passing**, plus 11 end-to-end against the rebuilt containers.
Phase 1 finished at 169 for the same suites.

The whole stack was rebuilt and restarted on the Phase 2 code: all seven Compose
services reached healthy, `migrate` applied `0002_phase_2_domain` to the existing
Phase 1 database, and a manual smoke test through the running API confirmed a
workflow can be created, an idea stored verbatim (em dash and apostrophe intact),
a second submission rejected with 409, and a gate decision on a `DRAFT` workflow
rejected with `gate-not-satisfied`.

### Static analysis

| Check | Result |
| --- | --- |
| `ruff format --check` (api, worker) | 72 files already formatted |
| `ruff check` (api, worker) | All checks passed |
| `mypy --strict` (api) | no issues in 71 source files |
| `mypy --strict` (worker) | no issues in 8 source files |
| `eslint . --max-warnings=0` | clean |
| `tsc --noEmit` ×3 + `vue-tsc --noEmit` | clean |
| `docker compose config --quiet` | valid |
| Playwright E2E vs. rebuilt containers | **11 passed** |

### What the Phase 2 tests actually prove

| Requirement | Test |
| --- | --- |
| All three idea modes | `test_ideas.py::TestModes`, `test_repositories.py::test_every_idea_mode_persists`, `test_api_workflows.py::test_creates_in_every_idea_mode` |
| Original idea immutability | `test_original_text_survives_revisions`, `test_editing_original_text_is_refused`, `test_second_submission_is_a_conflict` |
| Idea revisions | `test_revisions_are_numbered_and_ordered`, `test_duplicate_revision_number_is_refused` |
| Concept origin | `TestConceptOrigin`, `test_every_origin_persists`, `test_hybrid_holds_all_three_concept_origins` |
| Optimised concept stored separately | `test_user_concept_links_back_to_the_preserved_idea`, `test_optimized_concepts_are_stored_separately` |
| Prompt versioning | `test_prompt_versions_increment_and_persist`, `test_duplicate_prompt_version_is_refused` |
| Valid and invalid transitions | `TestTransitions` (every happy-path step parametrised) |
| All three gates | `TestGates` |
| Publication blocked without final approval | `TestPublicationIsHumanOnly` |
| Artwork blocked without idea approval | `test_artwork_blocked_before_idea_approval` |
| Production blocked without artwork approval | `test_production_blocked_before_artwork_approval` |
| Rejection and revision behaviour | `test_rejection_returns_to_the_producing_stage`, `test_revision_request_returns_to_a_producing_state`, `test_rejection_moves_back_and_is_kept` |
| Append-only approval history | `test_history_is_append_only`, `test_latest_decision_governs_the_gate` |
| Cost precision and aggregation | `test_money.py` (19 tests), `TestCostLedger` |
| Audit-event creation and redaction | `TestAuditLog` |
| Repository behaviour | `TestWorkflowRepository` |
| Database constraints | `TestDatabaseConstraints` (7 tests incl. PG enum rejection) |
| Migration upgrade | integration `conftest.py` runs down-then-up per session |
| API validation, 404, conflict | `test_api_workflows.py` (24 tests) |
| Fixture loading | `test_fixtures.py` (16 tests) |
| A low score never removes a user concept | `test_a_low_scoring_concept_is_kept`, `test_low_scoring_concept_is_kept` |

---

## Running the tests

Unit tests need nothing:

```bash
cd apps/api && ../../.venv/bin/python -m pytest -m "not integration" --ignore=tests/integration
```

Integration tests need PostgreSQL:

```bash
docker compose up -d postgres
docker compose exec postgres psql -U etsy -d postgres -c "CREATE DATABASE etsy_test;"
cd apps/api && TEST_DATABASE_URL="postgresql+asyncpg://etsy:etsy_local_password@localhost:5432/etsy_test" \
  ../../.venv/bin/python -m pytest
```

If no database is reachable the integration package **skips with a message
saying how to get one** — it never reports a skip as a pass.

Seed the fixtures:

```bash
cd apps/api && ../../.venv/bin/python -m app.fixtures.dev_seed
```

---

## Deferred work

- **Ownership enforcement.** `owner_id` is recorded but not checked. Any caller
  can create a workflow for any owner and read any workflow. Phase 3.
- **`ShopConnection`, `Mockup`, `Package`, standalone `IpReview`.** Belong to the
  phases that own them; the IP review is fields on `ListingDraft` until Phase 8.
- **Telegram entities.** Phase 4.
- **Outbox pattern.** Listed under Phase 2 in `TODO.md` but genuinely needs a
  dispatcher to be meaningful; carried to Phase 4/5 with the first real job.
- **`ProductionJob`, `ArtworkJob`, `Asset`, `ListingDraft` are schema only.** No
  code writes them outside tests.
- **Cost price configuration.** `price_reference` is a free-form JSONB column;
  the versioned price table with `effective_from` arrives with the first paid
  provider in Phase 5.

## Known limitations

- **No authentication.** Do not expose this build to a public address.
- **`GET /api/v1/workflows` has offset pagination**, not the cursor pagination
  `CLAUDE.md` specifies for growing collections. Fine at single-owner scale;
  revisit before the list is long.
- **The timeline endpoint loads a workflow's whole history** with a 200-event
  cap and no pagination.
- **`decide_gate` does not verify the target version is current.** The approval
  records `target_version`, but nothing yet rejects an approval whose target has
  since been edited. The data is there; the check belongs with the listing editor
  in Phase 8.
- **CI runs the integration suite in its own job**, added in this phase. It is
  not part of the `python` job, so a missing database cannot silently skip it.
- **`updated_at` uses a Python-side `onupdate`**, so a raw SQL UPDATE would not
  refresh it. All application writes go through the ORM.

## Cost impact

**Zero.** No paid API was called. `PROVIDER_MODE=live` is still rejected at
startup, the only provider the ledger can record is `FAKE`, and every fixture
cost entry is `0.00`.

---

## Recommended Phase 3 starting point

Phase 3 is **Authentication and settings** ([ADR-0002](../adr/0002-single-owner-authentication.md)).
Start with the two things Phase 2 deliberately left open:

1. **`owner_id` is recorded but not enforced.** Add single-owner authentication
   with Argon2id and a server-side session, then make every workflow route
   reject a caller who is not the owner. The column, the index and the
   relationship are already there.
2. **Secrets have nowhere to live yet.** Add `ShopConnection` and the provider
   settings tables with tokens encrypted at rest under a versioned key
   (`ENCRYPTION_KEY_VERSION` already exists in settings), and make sure no
   response model can return one — the `redact_secrets` processor and the audit
   redaction are already in place to build on.

Everything Phase 3 needs from the domain exists. It should not have to change a
single Phase 2 model.
