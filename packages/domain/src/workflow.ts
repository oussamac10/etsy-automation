/**
 * Shared workflow vocabulary for the TypeScript side of the monorepo.
 *
 * The *authoritative* state machine is implemented in Python
 * (`apps/api/src/app/domain/workflow.py`). This module mirrors it so the web
 * app and image worker can be typed against the same names. A contract test
 * (`apps/api/tests/test_workflow_contract.py`) fails if the two drift.
 */

/** Workflow states, in the order the workflow advances through them. */
export const RUN_STATUSES = [
  "DRAFT",
  "RESEARCH_QUEUED",
  "RESEARCHING",
  "IDEA_REVIEW",
  "IDEA_APPROVED",
  "ART_QUEUED",
  "ART_GENERATION",
  "ART_REVIEW",
  "ARTWORK_APPROVED",
  "PRODUCTION",
  "IP_REVIEW",
  "LISTING_REVIEW",
  "READY_FOR_ETSY_DRAFT",
  "ETSY_DRAFT_CREATED",
  "PUBLISHED",
  "CANCELLED",
] as const;

export type RunStatus = (typeof RUN_STATUSES)[number];

/** The happy path. Excludes PUBLISHED and CANCELLED, which leave it. */
export const HAPPY_PATH = [
  "DRAFT",
  "RESEARCH_QUEUED",
  "RESEARCHING",
  "IDEA_REVIEW",
  "IDEA_APPROVED",
  "ART_QUEUED",
  "ART_GENERATION",
  "ART_REVIEW",
  "ARTWORK_APPROVED",
  "PRODUCTION",
  "IP_REVIEW",
  "LISTING_REVIEW",
  "READY_FOR_ETSY_DRAFT",
  "ETSY_DRAFT_CREATED",
] as const satisfies readonly RunStatus[];

/**
 * Explicit, retryable failure states. Every phase can fail without losing the
 * work already approved, so failures are their own states rather than a flag.
 */
export const FAILURE_STATUSES = [
  "RESEARCH_FAILED",
  "ART_GENERATION_FAILED",
  "PRODUCTION_FAILED",
  "IP_REVIEW_FAILED",
  "ETSY_DRAFT_FAILED",
] as const;

export type FailureStatus = (typeof FAILURE_STATUSES)[number];

/** The three mandatory human gates. None of them may be skipped or automated. */
export const APPROVAL_GATES = [
  "IDEA_APPROVAL",
  "ARTWORK_APPROVAL",
  "LISTING_APPROVAL",
] as const;

export type ApprovalGate = (typeof APPROVAL_GATES)[number];

/** Gate outcomes. `PENDING` is an unanswered request, not a decision. */
export const APPROVAL_DECISIONS = [
  "PENDING",
  "APPROVED",
  "REJECTED",
  "REVISION_REQUESTED",
] as const;

export type ApprovalDecision = (typeof APPROVAL_DECISIONS)[number];

/** How a workflow gets its starting concept. Fixed at creation. */
export const IDEA_MODES = ["market-led", "user-idea", "hybrid"] as const;

export type IdeaMode = (typeof IDEA_MODES)[number];

/** Where a proposed concept came from. */
export const CONCEPT_ORIGINS = ["user", "market", "hybrid"] as const;

export type ConceptOrigin = (typeof CONCEPT_ORIGINS)[number];

/**
 * Risk vocabulary. `safe` is intentionally absent: the app never certifies that
 * a phrase or design is free of third-party rights.
 */
export const RISK_LEVELS = ["low", "medium", "high", "unknown"] as const;

export type RiskLevel = (typeof RISK_LEVELS)[number];

/** Job lifecycle shared by every queued/paid operation. */
export const JOB_STATUSES = [
  "QUEUED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

/** The state a workflow must be in before a given gate can be decided. */
export const GATE_SOURCE_STATUS: Readonly<Record<ApprovalGate, RunStatus>> =
  Object.freeze({
    IDEA_APPROVAL: "IDEA_REVIEW",
    ARTWORK_APPROVAL: "ART_REVIEW",
    LISTING_APPROVAL: "LISTING_REVIEW",
  });

/** Where an approved gate sends the workflow next. */
export const GATE_TARGET_STATUS: Readonly<Record<ApprovalGate, RunStatus>> =
  Object.freeze({
    IDEA_APPROVAL: "IDEA_APPROVED",
    ARTWORK_APPROVAL: "ARTWORK_APPROVED",
    LISTING_APPROVAL: "READY_FOR_ETSY_DRAFT",
  });

/** States nothing may leave. */
export const TERMINAL_STATUSES = ["PUBLISHED", "CANCELLED"] as const;

export function isRunStatus(value: string): value is RunStatus {
  return (RUN_STATUSES as readonly string[]).includes(value);
}

/**
 * The application's own work ends at a draft. `PUBLISHED` is only ever a record
 * that the owner published it in Etsy themselves.
 */
export function isTerminalSuccess(status: RunStatus): boolean {
  return status === "ETSY_DRAFT_CREATED";
}

/** True for a state that requires the owner to supply their own idea text. */
export function requiresOriginalIdea(mode: IdeaMode): boolean {
  return mode === "user-idea" || mode === "hybrid";
}
