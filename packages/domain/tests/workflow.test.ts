import { describe, expect, it } from "vitest";
import {
  APPROVAL_DECISIONS,
  APPROVAL_GATES,
  CONCEPT_ORIGINS,
  GATE_SOURCE_STATUS,
  GATE_TARGET_STATUS,
  HAPPY_PATH,
  IDEA_MODES,
  RISK_LEVELS,
  RUN_STATUSES,
  TERMINAL_STATUSES,
  isRunStatus,
  isTerminalSuccess,
  requiresOriginalIdea,
} from "../src/workflow.js";

describe("workflow vocabulary", () => {
  it("declares the fourteen happy-path states in the authoritative order", () => {
    expect(HAPPY_PATH).toEqual([
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
    ]);
  });

  it("adds the two off-path states after the happy path", () => {
    expect(RUN_STATUSES).toHaveLength(HAPPY_PATH.length + 2);
    // CANCELLED is not terminal: a stopped campaign can be rerun.
    expect(TERMINAL_STATUSES).toEqual(["PUBLISHED"]);
  });

  it("declares exactly three human gates", () => {
    expect(APPROVAL_GATES).toHaveLength(3);
  });

  it("maps every gate to a review state that exists", () => {
    for (const gate of APPROVAL_GATES) {
      expect(isRunStatus(GATE_SOURCE_STATUS[gate])).toBe(true);
      expect(isRunStatus(GATE_TARGET_STATUS[gate])).toBe(true);
    }
  });

  it("never lets a gate approval reach PUBLISHED", () => {
    for (const gate of APPROVAL_GATES) {
      expect(GATE_TARGET_STATUS[gate]).not.toBe("PUBLISHED");
    }
  });

  it("never offers a 'safe' risk level", () => {
    expect(RISK_LEVELS).not.toContain("safe");
    expect(RISK_LEVELS).toEqual(["low", "medium", "high", "unknown"]);
  });

  it("treats only ETSY_DRAFT_CREATED as terminal success", () => {
    // PUBLISHED is a record that the owner published it themselves, not
    // something the application achieved.
    expect(isTerminalSuccess("ETSY_DRAFT_CREATED")).toBe(true);
    expect(isTerminalSuccess("PUBLISHED")).toBe(false);
    expect(isTerminalSuccess("LISTING_REVIEW")).toBe(false);
  });

  it("rejects unknown status strings", () => {
    expect(isRunStatus("SHIPPED")).toBe(false);
    expect(isRunStatus("PUBLISHED")).toBe(true);
  });
});

describe("idea modes", () => {
  it("declares exactly three modes", () => {
    expect(IDEA_MODES).toEqual(["market-led", "user-idea", "hybrid"]);
  });

  it("knows which modes need the owner's own text", () => {
    expect(requiresOriginalIdea("market-led")).toBe(false);
    expect(requiresOriginalIdea("user-idea")).toBe(true);
    expect(requiresOriginalIdea("hybrid")).toBe(true);
  });

  it("declares the three concept origins", () => {
    expect(CONCEPT_ORIGINS).toEqual(["user", "market", "hybrid"]);
  });
});

describe("approval decisions", () => {
  it("treats PENDING as a distinct, non-decided state", () => {
    expect(APPROVAL_DECISIONS).toEqual([
      "PENDING",
      "APPROVED",
      "REJECTED",
      "REVISION_REQUESTED",
    ]);
  });
});
