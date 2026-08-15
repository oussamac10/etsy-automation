import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { runQaReport } from "../src/qa.js";
import { DEFAULT_PRINT_PROFILE } from "../src/profiles.js";

describe("runQaReport", () => {
  it("passes QA for a valid 4500x5400 transparent PNG with centered content and 300 DPI", async () => {
    const innerGraphic = await sharp({
      create: {
        width: 2000,
        height: 2000,
        channels: 4,
        background: { r: 80, g: 120, b: 240, alpha: 1 },
      },
    })
      .png()
      .toBuffer();

    const masterPng = await sharp({
      create: {
        width: 4500,
        height: 5400,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      },
    })
      .composite([{ input: innerGraphic, left: 1250, top: 1700 }])
      .png()
      .withMetadata({ density: 300 })
      .toBuffer();

    const report = await runQaReport(new Uint8Array(masterPng), {
      profile: DEFAULT_PRINT_PROFILE,
      exactSlogan: "Do Epic Shit",
    });

    expect(report.qa_passed).toBe(true);
    expect(report.dimensions_valid).toBe(true);
    expect(report.width).toBe(4500);
    expect(report.height).toBe(5400);
    expect(report.density_dpi).toBe(300);
    expect(report.has_alpha).toBe(true);
    expect(report.has_transparent_pixels).toBe(true);
    expect(report.transparent_background_valid).toBe(true);
    expect(report.safe_margins_valid).toBe(true);
    expect(report.cropped_edges_detected).toBe(false);
    expect(report.typography_applied).toBe(true);
    expect(report.exact_slogan_recorded).toBe("Do Epic Shit");
    expect(report.warnings).toEqual([]);
  });

  it("flags invalid dimensions and opaque background", async () => {
    const opaqueWrongSize = await sharp({
      create: {
        width: 800,
        height: 800,
        channels: 3,
        background: { r: 255, g: 255, b: 255 },
      },
    })
      .png()
      .toBuffer();

    const report = await runQaReport(new Uint8Array(opaqueWrongSize));
    expect(report.qa_passed).toBe(false);
    expect(report.dimensions_valid).toBe(false);
    expect(report.has_transparent_pixels).toBe(false);
    expect(report.warnings.length).toBeGreaterThan(0);
  });
});
