/**
 * Shared workflow vocabulary for the TypeScript side of the monorepo.
 *
 * The *authoritative* state machine is implemented in Python
 * (`apps/api/src/app/domain/workflow.py`). This module mirrors it so the web
 * app and image worker can be typed against the same names. A contract test
 * (`tests/contracts/workflow_contract_test.py`) fails if the two drift.
 */

/** Workflow states, in the order the run advances through them. */
export const RUN_STATUSES = [
  "RESEARCHING",
  "IDEA_REVIEW",
  "ART_GENERATION",
  "ART_REVIEW",
  "PRODUCTION",
  "IP_REVIEW",
  "LISTING_REVIEW",
  "ETSY_DRAFT_CREATED",
] as const;

export type RunStatus = (typeof RUN_STATUSES)[number];

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

export type ApprovalDecision = "APPROVED" | "REJECTED";

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

/** The state a run must be in before a given gate can be decided. */
export const GATE_SOURCE_STATUS: Readonly<Record<ApprovalGate, RunStatus>> =
  Object.freeze({
    IDEA_APPROVAL: "IDEA_REVIEW",
    ARTWORK_APPROVAL: "ART_REVIEW",
    LISTING_APPROVAL: "LISTING_REVIEW",
  });

export function isRunStatus(value: string): value is RunStatus {
  return (RUN_STATUSES as readonly string[]).includes(value);
}

export function isTerminalSuccess(status: RunStatus): boolean {
  return status === "ETSY_DRAFT_CREATED";
}
