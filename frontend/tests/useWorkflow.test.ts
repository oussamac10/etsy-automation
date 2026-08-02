import { describe, expect, it } from "vitest";
import { FALLBACK_STATES, parseWorkflow } from "../composables/useWorkflow";

const valid = {
  states: ["RESEARCHING", "IDEA_REVIEW"],
  failure_states: ["RESEARCH_FAILED"],
  gates: [
    {
      gate: "IDEA_APPROVAL",
      decided_from: "IDEA_REVIEW",
      advances_to: "ART_GENERATION",
    },
  ],
  risk_levels: ["low", "medium", "high", "unknown"],
  publishes_automatically: false,
};

describe("parseWorkflow", () => {
  it("accepts a well-formed description", () => {
    expect(parseWorkflow(valid).states).toEqual(["RESEARCHING", "IDEA_REVIEW"]);
  });

  it("refuses a payload that claims automatic publishing", () => {
    expect(() =>
      parseWorkflow({ ...valid, publishes_automatically: true }),
    ).toThrow(/automatic publishing/);
  });

  it("rejects an empty state list", () => {
    expect(() => parseWorkflow({ ...valid, states: [] })).toThrow();
  });

  it("rejects a malformed gate", () => {
    expect(() =>
      parseWorkflow({ ...valid, gates: [{ gate: "IDEA_APPROVAL" }] }),
    ).toThrow();
  });
});

describe("FALLBACK_STATES", () => {
  it("is the shared domain pipeline", () => {
    // Phase 2 extended the pipeline: it starts at DRAFT, and PUBLISHED /
    // CANCELLED sit after the happy path rather than on it.
    expect(FALLBACK_STATES[0]).toBe("DRAFT");
    expect(FALLBACK_STATES).toContain("ETSY_DRAFT_CREATED");
    expect(FALLBACK_STATES).toHaveLength(16);
  });
});
