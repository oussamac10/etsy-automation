import { describe, expect, it } from "vitest";
import {
  APPROVAL_GATES,
  GATE_SOURCE_STATUS,
  RISK_LEVELS,
  RUN_STATUSES,
  isRunStatus,
  isTerminalSuccess,
} from "../src/workflow.js";

describe("workflow vocabulary", () => {
  it("declares the eight states in the authoritative order", () => {
    expect(RUN_STATUSES).toEqual([
      "RESEARCHING",
      "IDEA_REVIEW",
      "ART_GENERATION",
      "ART_REVIEW",
      "PRODUCTION",
      "IP_REVIEW",
      "LISTING_REVIEW",
      "ETSY_DRAFT_CREATED",
    ]);
  });

  it("declares exactly three human gates", () => {
    expect(APPROVAL_GATES).toHaveLength(3);
  });

  it("maps every gate to a review state that exists", () => {
    for (const gate of APPROVAL_GATES) {
      expect(isRunStatus(GATE_SOURCE_STATUS[gate])).toBe(true);
    }
  });

  it("never offers a 'safe' risk level", () => {
    expect(RISK_LEVELS).not.toContain("safe");
    expect(RISK_LEVELS).toEqual(["low", "medium", "high", "unknown"]);
  });

  it("treats only ETSY_DRAFT_CREATED as terminal success", () => {
    expect(isTerminalSuccess("ETSY_DRAFT_CREATED")).toBe(true);
    expect(isTerminalSuccess("LISTING_REVIEW")).toBe(false);
  });

  it("rejects unknown status strings", () => {
    expect(isRunStatus("PUBLISHED")).toBe(false);
  });
});
