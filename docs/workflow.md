# Workflow

The state machine is authoritative. It is implemented in
`apps/api/src/app/domain/workflow.py`, mirrored for TypeScript in
`packages/domain/src/workflow.ts`, and exposed read-only at
`GET /api/v1/workflow`.

> **Phase 2 extended the pipeline from eight states to sixteen.** This page is
> the summary; the complete transition table, the rejection/revision routing and
> the stage guards are in
> [`workflow-state-machine.md`](workflow-state-machine.md).

## The pipeline

```text
DRAFT
  → RESEARCH_QUEUED
  → RESEARCHING
  → IDEA_REVIEW           ← human gate 1
  → IDEA_APPROVED
  → ART_QUEUED
  → ART_GENERATION
  → ART_REVIEW            ← human gate 2
  → ARTWORK_APPROVED
  → PRODUCTION
  → IP_REVIEW
  → LISTING_REVIEW        ← human gate 3
  → READY_FOR_ETSY_DRAFT
  → ETSY_DRAFT_CREATED
```

Two states sit off the happy path: `CANCELLED` (reachable from any live state)
and `PUBLISHED`.

`ETSY_DRAFT_CREATED` is where the **application's** work ends. `PUBLISHED` exists
only so the owner can record that they published the draft in Etsy themselves —
it is reachable from `ETSY_DRAFT_CREATED` and nowhere else, no gate approval
targets it, and `EtsyGateway` still has no publish method. Publishing is always
an action a person takes in Etsy.

## Transition rules

The happy path advances one state at a time. On top of that, any live workflow
may be cancelled, and queued work may be withdrawn before it runs. `advance()`
refuses to skip, refuses to move backwards, refuses to leave a terminal state,
and refuses to leave a gated state at all.

```python
advance(RunStatus.RESEARCHING, RunStatus.IDEA_REVIEW)      # ok
advance(RunStatus.RESEARCH_QUEUED, RunStatus.DRAFT)        # ok — job withdrawn
advance(RunStatus.PRODUCTION, RunStatus.CANCELLED)         # ok — owner cancels
advance(RunStatus.ART_GENERATION, RunStatus.PRODUCTION)    # IllegalTransitionError — skips ART_REVIEW
advance(RunStatus.IDEA_REVIEW, RunStatus.IDEA_APPROVED)    # IllegalTransitionError — gated
advance(RunStatus.PUBLISHED, RunStatus.LISTING_REVIEW)     # IllegalTransitionError — terminal
```

The last case matters most: the only way out of a review state is
`apply_approval()`. A gate cannot be bypassed by a state change, which is what
makes "never skip these three gates" a property of the code rather than a note
in a document.

## The three human gates

| Gate | Decided from | Approved → | Rejected → | Revision requested → |
|---|---|---|---|---|
| `IDEA_APPROVAL` | `IDEA_REVIEW` | `IDEA_APPROVED` | `DRAFT` | `RESEARCH_QUEUED` |
| `ARTWORK_APPROVAL` | `ART_REVIEW` | `ARTWORK_APPROVED` | `IDEA_APPROVED` | `ART_QUEUED` |
| `LISTING_APPROVAL` | `LISTING_REVIEW` | `READY_FOR_ETSY_DRAFT` | `ARTWORK_APPROVED` | `PRODUCTION` |

A rejection says "not this artefact" and returns the workflow to the stage that
produced it. A revision request says "this artefact, but changed" and returns to
the nearest state that can produce a new version. Neither ever advances the
workflow, and neither dispatches a paid child job.

```python
apply_approval(IDEA_REVIEW, IDEA_APPROVAL, decision=APPROVED)
# → RunStatus.IDEA_APPROVED

apply_approval(IDEA_REVIEW, IDEA_APPROVAL, decision=REJECTED)
# → RunStatus.DRAFT   (research is redone; no artwork job is dispatched)

apply_approval(IDEA_REVIEW, IDEA_APPROVAL, decision=PENDING)
# → IllegalTransitionError   (a pending request is not a decision)

apply_approval(IP_REVIEW, LISTING_APPROVAL, decision=APPROVED)
# → GateNotSatisfiedError   (IP review cannot be skipped)
```

A rejection is not a failure — the workflow is healthy, the artefact was not
wanted. Either way no paid child job is dispatched: a rejected idea can never
generate artwork, and rejected artwork can never enter production. Three guards
enforce that from anywhere in the codebase:

```python
require_idea_approved(state)      # Artwork generation needs gate 1
require_artwork_approved(state)   # Production needs gate 2
require_listing_approved(state)   # Etsy draft creation needs gate 3
```

An approval records the **version** of what was reviewed (`target_type`,
`target_id`, `target_version`), not just an entity ID. The columns are populated
from Phase 2; the check that rejects an approval whose target has since been
edited lands with the listing editor in Phase 8.

Approval history is append-only: changing your mind writes another row, and
`is_approved()` reads the *most recent* decision, so a later rejection or
revision request actually revokes the gate.

### Gate 3 is two decisions

`LISTING_APPROVAL` covers both the IP acknowledgement and the final listing
approval. The owner must explicitly acknowledge that the preliminary IP review
is *not* a clearance search and not legal advice. The system never concludes
that a phrase or design is free of third-party rights; `RiskLevel` has no `safe`
member for exactly this reason — only `low`, `medium`, `high` and `unknown`.

## Failure states

Every stage that can fail has its own state, so a failure never loses the work
already approved and always knows where to resume.

| Failure state | Raised from | Retry resumes at |
|---|---|---|
| `RESEARCH_FAILED` | `RESEARCHING` | `RESEARCHING` |
| `ART_GENERATION_FAILED` | `ART_GENERATION` | `ART_GENERATION` |
| `PRODUCTION_FAILED` | `PRODUCTION` | `PRODUCTION` |
| `IP_REVIEW_FAILED` | `IP_REVIEW` | `IP_REVIEW` |
| `ETSY_DRAFT_FAILED` | `READY_FOR_ETSY_DRAFT` | `READY_FOR_ETSY_DRAFT` |

```python
state = fail(RunStatus.ART_GENERATION, FailureStatus.ART_GENERATION_FAILED)
retry(state)   # → RunStatus.ART_GENERATION
```

A failure can only be raised from its own origin, so a bug cannot park a run in
an unrelated failure state and lose the trail.

## Job semantics

Queue delivery is at least once, so every handler must be idempotent.

- **Idempotency key** — derived from the inputs that determine the result
  (`worker/idempotency.py`), with the run ID as scope. The same message
  delivered twice produces the same key, and a paid operation is billed once.
  Keys never contain a secret.
- **Retry policy** — `worker/retry.py`. Only failures an adapter classified as
  `retryable` or `rate_limited` are retried; `invalid_request`,
  `authentication`, `budget_exceeded` and `permanent` never are, and neither is
  an unclassified exception. A provider's `retry-after` wins over the computed
  delay; otherwise exponential backoff with jitter, capped, with a maximum
  attempt count.
- **Exhaustion** — a job that runs out of attempts moves to a visible failed
  state. Nothing loops forever.
- **Gate coupling** — a paid child job is never dispatched when its parent gate
  is unapproved.

## Costs

Every paid operation is estimated before dispatch, reserved against the run
budget, and reconciled against recorded usage afterwards. A job that would
exceed the run or monthly budget is rejected until the owner approves an
override, and the system never silently falls back to a more expensive model.

Money is `Decimal` or integer minor units — never a float. See
[`API_COSTS.md`](API_COSTS.md).

## Audit

Approvals, audit events, provider usage and provenance records are never deleted
through normal application flows. Every provider call, approval, retry and
external ID is recorded with a correlation ID.

From Phase 2 this is structural rather than a rule: those tables have no
`updated_at`, and their repositories expose no update or delete method. Audit
metadata passes through the same redaction the logger uses before it is written.

Every state change also writes a `WorkflowTransition` row, so
`GET /api/v1/workflows/{id}/timeline` can replay what happened without
reconstructing it from the audit log.

## Implementation status

Phase 1 implemented the state machine, its invariants, the failure/retry model,
the retry policy and idempotency-key derivation.

Phase 2 extended the machine to sixteen states, added the stage guards
(`require_idea_approved`, `require_artwork_approved`, `require_listing_approved`)
and persisted all of it: workflows with an optimistic-lock version, an
append-only transition timeline, append-only approvals, the cost ledger and the
audit log. Every transition and gate outcome is covered by tests, and compare-
and-set rejects a decision made against a stale version.

The gates become real UI in Phases 5, 6 and 8.
