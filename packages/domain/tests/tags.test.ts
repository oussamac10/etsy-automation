import { describe, expect, it } from "vitest";
import { MAX_ETSY_TAGS, normalizeTag, validateTags } from "../src/tags.js";

describe("normalizeTag", () => {
  it.each([
    ["  Boho Sunflower  ", "boho sunflower"],
    ["Boho   Sunflower", "boho sunflower"],
    ["PNG", "png"],
  ])("normalises %j to %j", (input, expected) => {
    expect(normalizeTag(input)).toBe(expected);
  });
});

describe("validateTags", () => {
  it("accepts a valid list", () => {
    const result = validateTags(["sunflower png", "boho wall art", "digital"]);
    expect(result.valid).toBe(true);
    expect(result.tags).toEqual(["sunflower png", "boho wall art", "digital"]);
    expect(result.errors).toEqual([]);
  });

  it("rejects tags longer than 20 characters", () => {
    const result = validateTags(["a".repeat(21)]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain("exceeds 20 characters");
  });

  it("rejects unsupported characters", () => {
    const result = validateTags(["sunflower!"]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain("unsupported characters");
  });

  it("rejects duplicates only after normalisation", () => {
    const result = validateTags(["Sunflower PNG", "sunflower   png"]);
    expect(result.valid).toBe(false);
    expect(result.tags).toEqual(["sunflower png"]);
    expect(result.errors[0]).toContain("duplicated");
  });

  it("rejects more than the Etsy limit", () => {
    const many = Array.from({ length: MAX_ETSY_TAGS + 1 }, (_, i) => `tag ${i}`);
    const result = validateTags(many);
    expect(result.valid).toBe(false);
    expect(result.errors.at(-1)).toContain(`limit is ${MAX_ETSY_TAGS}`);
  });

  it("accepts exactly the Etsy limit", () => {
    const exact = Array.from({ length: MAX_ETSY_TAGS }, (_, i) => `tag ${i}`);
    expect(validateTags(exact).valid).toBe(true);
  });

  it("reports every violation rather than stopping at the first", () => {
    const result = validateTags(["", "b".repeat(30), "ok tag"]);
    expect(result.errors).toHaveLength(2);
    expect(result.tags).toEqual(["ok tag"]);
  });
});
