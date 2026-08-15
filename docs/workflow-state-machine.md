# Workflow state machine

The complete transition table and the rules around it. Implemented in
[`backend/app/domain/workflow.py`](../backend/app/domain/workflow.py),
mirrored for TypeScript in `packages/domain/src/workflow.ts`, and exposed
read-only at `GET /api/v1/workflow`.

A contract test parses the TypeScript file and fails if the two drift.

---

## States

Phase 1 defined eight states. Phase 2 extended the pipeline to sixteen: every
Phase 1 name is preserved with its original meaning, and the new states name
moments Phase 1 collapsed together.

### Happy path, in order

| # | State | Meaning | New in Phase 2 |
| --- | --- | --- | --- |
| 1 | `DRAFT` | Created, brief captured, nothing dispatched | ✅ |
| 2 | `RESEARCH_QUEUED` | Research job enqueued, not started | ✅ |
| 3 | `RESEARCHING` | Research running | |
| 4 | `IDEA_REVIEW` | **Gate 1** — ranked concepts awaiting a person | |
| 5 | `IDEA_APPROVED` | Gate 1 approved; concept and prompt version frozen | ✅ |
| 6 | `ART_QUEUED` | Artwork job enqueued, not started | ✅ |
| 7 | `ART_GENERATION` | Generation running | |
| 8 | `ART_REVIEW` | **Gate 2** — alternatives awaiting a person | |
| 9 | `ARTWORK_APPROVED` | Gate 2 approved; chosen asset frozen | ✅ |
| 10 | `PRODUCTION` | Background, trim, typography, upscale, mockups, QA | |
| 11 | `IP_REVIEW` | Preliminary phrase and IP risk review | |
| 12 | `LISTING_REVIEW` | **Gate 3** — listing, package and IP acknowledgement | |
| 13 | `READY_FOR_ETSY_DRAFT` | Gate 3 approved; everything validated | ✅ |
| 14 | `ETSY_DRAFT_CREATED` | A draft exists in Etsy. **The automated work ends here** | |

### Off the happy path

| State | Meaning |
| --- | --- |
| `PUBLISHED` | The owner published the draft **themselves** and told us. Terminal |
| `CANCELLED` | Abandoned by the owner. Terminal |

### Failure states

Explicit and retryable, each from its own stage.

| Failure state | Raised from | Retry resumes at |
| --- | --- | --- |
| `RESEARCH_FAILED` | `RESEARCHING` | `RESEARCHING` |
| `ART_GENERATION_FAILED` | `ART_GENERATION` | `ART_GENERATION` |
| `PRODUCTION_FAILED` | `PRODUCTION` | `PRODUCTION` |
| `IP_REVIEW_FAILED` | `IP_REVIEW` | `IP_REVIEW` |
| `ETSY_DRAFT_FAILED` | `READY_FOR_ETSY_DRAFT` | `READY_FOR_ETSY_DRAFT` |

Per-stage failure states rather than one generic `FAILED`: a failure must never
lose the work already approved, and it must know where to resume. A failure can
only be raised from its own origin, so a bug cannot park a workflow in an
unrelated failure state and lose the trail.

---

## The complete transition table

`advance(current, requested)` permits exactly these moves. Anything else raises
`IllegalTransitionError`.

| From | To | Trigger |
| --- | --- | --- |
| `DRAFT` | `RESEARCH_QUEUED` | research enqueued |
| `DRAFT` | `CANCELLED` | owner cancels |
| `RESEARCH_QUEUED` | `RESEARCHING` | worker picks the job up |
| `RESEARCH_QUEUED` | `DRAFT` | job withdrawn before it ran |
| `RESEARCH_QUEUED` | `CANCELLED` | owner cancels |
| `RESEARCHING` | `IDEA_REVIEW` | research completed |
| `RESEARCHING` | `CANCELLED` | owner cancels |
| `IDEA_REVIEW` | **gate only** | see gate table below |
| `IDEA_REVIEW` | `CANCELLED` | owner cancels |
| `IDEA_APPROVED` | `ART_QUEUED` | artwork enqueued |
| `IDEA_APPROVED` | `CANCELLED` | owner cancels |
| `ART_QUEUED` | `ART_GENERATION` | worker picks the job up |
| `ART_QUEUED` | `IDEA_APPROVED` | job withdrawn before it ran |
| `ART_QUEUED` | `CANCELLED` | owner cancels |
| `ART_GENERATION` | `ART_REVIEW` | generation completed |
| `ART_GENERATION` | `CANCELLED` | owner cancels |
| `ART_REVIEW` | **gate only** | see gate table below |
| `ART_REVIEW` | `CANCELLED` | owner cancels |
| `ARTWORK_APPROVED` | `PRODUCTION` | production started |
| `ARTWORK_APPROVED` | `CANCELLED` | owner cancels |
| `PRODUCTION` | `IP_REVIEW` | production completed |
| `PRODUCTION` | `CANCELLED` | owner cancels |
| `IP_REVIEW` | `LISTING_REVIEW` | IP screen recorded |
| `IP_REVIEW` | `CANCELLED` | owner cancels |
| `LISTING_REVIEW` | **gate only** | see gate table below |
| `LISTING_REVIEW` | `CANCELLED` | owner cancels |
| `READY_FOR_ETSY_DRAFT` | `ETSY_DRAFT_CREATED` | draft created in Etsy |
| `READY_FOR_ETSY_DRAFT` | `CANCELLED` | owner cancels |
| `ETSY_DRAFT_CREATED` | `PUBLISHED` | **the owner reports they published it** |
| `ETSY_DRAFT_CREATED` | `CANCELLED` | owner cancels |
| `PUBLISHED` | — | terminal |
| `CANCELLED` | — | terminal |

Two properties fall out of this table and are asserted directly:

- **Every state is reachable** from `DRAFT`, and the terminal states have no exit.
- **`PUBLISHED` is reachable only from `ETSY_DRAFT_CREATED`**, so a workflow can
  never be marked published without a draft existing first.

---

## The three human gates

Leaving a review state requires `apply_approval()`. `advance()` refuses it
outright — that is what makes "never skip these three gates" a property of the
code rather than a note in a document.

| Gate | Decided from | Approved → | Rejected → | Revision requested → |
| --- | --- | --- | --- | --- |
| `IDEA_APPROVAL` | `IDEA_REVIEW` | `IDEA_APPROVED` | `DRAFT` | `RESEARCH_QUEUED` |
| `ARTWORK_APPROVAL` | `ART_REVIEW` | `ARTWORK_APPROVED` | `IDEA_APPROVED` | `ART_QUEUED` |
| `LISTING_APPROVAL` | `LISTING_REVIEW` | `READY_FOR_ETSY_DRAFT` | `ARTWORK_APPROVED` | `PRODUCTION` |

### Why rejection and revision differ

A **rejection** says "not this artefact". It returns the workflow to the stage
that produced it, so the work is redone from further back: rejecting the ranked
concepts means the research itself must be redone.

A **revision request** says "this artefact, but changed". It returns to the
nearest state that can produce a new version — the same research run, the same
approved idea, the same approved artwork.

Neither ever advances the workflow. Both are asserted to land *earlier* on the
happy path than the gate they left.

`PENDING` is not a decision. Passing it to `apply_approval` raises, because a
request awaiting an answer must not be able to move anything.

### The gate decision is one transaction

`decide_gate` writes the `Approval` row, moves the workflow and writes the audit
event together. An approval that did not move the workflow, or a move with no
approval behind it, would both be lies about what happened.

The repository's `transition()` normally refuses to leave a gated state. A caller
acting on a decision passes the gate and decision, and the move is validated by
`apply_approval` instead — so a gated state can still only be left by a recorded
decision, never by an arbitrary request.

---

## Stage guards

The transition table stops a workflow *walking* past a gate. The guards stop any
code path *starting* a stage before its gate was approved, from anywhere:

```python
require_idea_approved(state)      # Artwork generation needs gate 1
require_artwork_approved(state)   # Production needs gate 2
require_listing_approved(state)   # Etsy draft creation needs gate 3
```

Each raises `GateNotApprovedError` unless the workflow has reached — or passed —
the state that gate's approval produces. Cancelled and off-path workflows are
refused too.

---

## Publication is a human action

The application creates **drafts**. It never publishes.

- `EtsyGateway` has no publish or activate method. The capability does not exist
  in the type system, which is stronger than a policy comment.
- No gate approval targets `PUBLISHED`.
- `is_terminal_success()` returns true for `ETSY_DRAFT_CREATED` only. `PUBLISHED`
  is not the application succeeding at something; it is a record of what the
  owner did in Etsy.
- Etsy charges a listing fee at publication, which is another reason that action
  stays with a person.

The `ETSY_DRAFT_CREATED → PUBLISHED` transition exists so the owner can tell the
system "I published this", and so later phases can attach performance data to a
listing that is actually live.

---

## Concurrency

`ProductWorkflow.version` is an optimistic lock. Every state change goes through
a conditional `UPDATE ... WHERE id = :id AND version = :expected`. If another
request moved the workflow in between, zero rows match and
`ConcurrentModificationError` is raised — the caller's decision is rejected as
stale rather than applied on top of someone else's change.

The domain validates the move **before** the UPDATE, so an illegal transition
never reaches the database.

---

## Risk vocabulary

`RiskLevel` is `low`, `medium`, `high` or `unknown`. **`safe` is deliberately not
a member.** The product never certifies that a phrase or design is free of
third-party rights, and there is no value it could store to say so.

---

## Where this is tested

| Guarantee | Test |
| --- | --- |
| Happy path order and reachability | `tests/test_workflow.py::TestStates` |
| Every permitted and forbidden transition | `TestTransitions` |
| Gates cannot be bypassed by a state change | `test_a_gated_state_cannot_be_advanced_directly` |
| Approval, rejection, revision outcomes | `TestGates` |
| Artwork blocked without gate 1, production without gate 2, drafts without gate 3 | `TestStageGuards` |
| Publication reachable only from a created draft | `TestPublicationIsHumanOnly` |
| Failure and retry from every stage | `TestFailureAndRetry` |
| Compare-and-set rejects a stale version | `tests/integration/test_repositories.py::test_stale_version_is_rejected` |
| Illegal transition writes nothing | `test_illegal_transition_is_refused_before_any_write` |
| TypeScript mirror matches | `tests/test_workflow_contract.py` |
