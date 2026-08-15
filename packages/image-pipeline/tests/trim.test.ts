import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { trimAndPad } from "../src/trim.js";
import { inspectImage } from "../src/inspect.js";
import { transparentSquare, opaqueSquare } from "./fixtures.js";

describe("trimAndPad", () => {
  it("trims excess transparent padding and adds specified margin", async () => {
    // Create a 200x200 canvas with a 60x60 square in the center
    const innerSquare = await sharp({
      create: {
        width: 60,
        height: 60,
        channels: 4,
        background: { r: 255, g: 100, b: 50, alpha: 1 },
      },
    })
      .png()
      .toBuffer();

    const canvas = await sharp({
      create: {
        width: 200,
        height: 200,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      },
    })
      .composite([{ input: innerSquare, left: 70, top: 70 }])
      .png()
      .toBuffer();

    const result = await trimAndPad(new Uint8Array(canvas), { marginPercent: 10 });
    expect(result.trimmedWidth).toBe(62); // 60 + 2 safety border
    expect(result.trimmedHeight).toBe(62);
    expect(result.paddedWidth).toBeGreaterThan(62);

    const facts = await inspectImage(result.buffer);
    expect(facts.hasAlpha).toBe(true);
    expect(facts.hasTransparentPixels).toBe(true);
    expect(facts.edgeMargins.top).toBeGreaterThan(0);
    expect(facts.edgeMargins.left).toBeGreaterThan(0);
  });

  it("handles opaque images safely without crashing", async () => {
    const opaque = await opaqueSquare(100);
    const result = await trimAndPad(new Uint8Array(opaque));
    expect(result.originalWidth).toBe(100);
    expect(result.paddedWidth).toBeGreaterThanOrEqual(100);
  });

  it("handles fully transparent image without crashing", async () => {
    const transparent = await transparentSquare(64);
    const result = await trimAndPad(new Uint8Array(transparent));
    expect(result.originalWidth).toBe(64);
  });
});
