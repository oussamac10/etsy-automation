# Workflow

The state machine is authoritative. It is implemented in
`apps/api/src/app/domain/workflow.py`, mirrored for TypeScript in
`packages/domain/src/workflow.ts`, and exposed read-only at
`GET /api/v1/workflow`.

## The pipeline

```text
RESEARCHING
  → IDEA_REVIEW          ← human gate 1
  → ART_GENERATION
  → ART_REVIEW           ← human gate 2
  → PRODUCTION
  → IP_REVIEW
  → LISTING_REVIEW       ← human gate 3
  → ETSY_DRAFT_CREATED
```

`ETSY_DRAFT_CREATED` is the end. There is no `PUBLISHED`, `ACTIVE` or `LIVE`
state, and no code path that could reach one — `EtsyGateway` has no publish
method. Publishing is always a separate action a person takes in Etsy.

## Transition rules

Movement is strictly linear: a state may only advance to its immediate
successor. `advance()` refuses to move backwards, refuses to skip, and refuses
to leave a gated state at all.

```python
advance(RunStatus.RESEARCHING, RunStatus.IDEA_REVIEW)     # ok
advance(RunStatus.ART_GENERATION, RunStatus.PRODUCTION)   # IllegalTransitionError — skips ART_REVIEW
advance(RunStatus.IDEA_REVIEW, RunStatus.ART_GENERATION)  # IllegalTransitionError — gated
```

The last case matters most: the only way out of a review state is
`apply_approval()`. A gate cannot be bypassed by a state change, which is what
makes "never skip these three gates" a property of the code rather than a note
in a document.

## The three human gates

| Gate | Decided from | Approval advances to | Rejection |
|---|---|---|---|
| `IDEA_APPROVAL` | `IDEA_REVIEW` | `ART_GENERATION` | stays in `IDEA_REVIEW` |
| `ARTWORK_APPROVAL` | `ART_REVIEW` | `PRODUCTION` | stays in `ART_REVIEW` |
| `LISTING_APPROVAL` | `LISTING_REVIEW` | `ETSY_DRAFT_CREATED` | stays in `LISTING_REVIEW` |

```python
apply_approval(RunStatus.IDEA_REVIEW, ApprovalGate.IDEA_APPROVAL, approved=True)
# → RunStatus.ART_GENERATION

apply_approval(RunStatus.IDEA_REVIEW, ApprovalGate.IDEA_APPROVAL, approved=False)
# → RunStatus.IDEA_REVIEW   (the owner iterates; no artwork job is dispatched)

apply_approval(RunStatus.IP_REVIEW, ApprovalGate.LISTING_APPROVAL, approved=True)
# → GateNotSatisfiedError   (IP review cannot be skipped)
```

A rejection is not a failure. It leaves the run where it is so the owner can
revise, and it means no paid child job is dispatched — a rejected idea can never
generate artwork, and rejected artwork can never enter production.

From Phase 2 an approval records the **immutable version or hash** of what was
approved, not just an entity ID, so editing something after approval invalidates
the approval instead of silently inheriting it.

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
| `ETSY_DRAFT_FAILED` | `LISTING_REVIEW` | `LISTING_REVIEW` |

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

## Implementation status

Phase 1 implements the state machine, its invariants, the failure/retry model,
the retry policy and idempotency-key derivation, all covered by unit tests.
Persistence of runs, approvals and the audit log arrives in Phase 2; the gates
become real UI in Phases 4, 5 and 7.
