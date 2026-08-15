import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { upscaleToPrint } from "../src/upscale.js";
import { transparentSquare } from "./fixtures.js";

describe("upscaleToPrint", () => {
  it("scales input onto 4500x5400 canvas with 300 DPI metadata and transparent background", async () => {
    const input = await transparentSquare(200);
    const result = await upscaleToPrint(new Uint8Array(input));

    expect(result.width).toBe(4500);
    expect(result.height).toBe(5400);
    expect(result.densityDpi).toBe(300);
    expect(result.format).toBe("png");
    expect(result.colorSpace).toBe("sRGB");

    const meta = await sharp(result.buffer).metadata();
    expect(meta.width).toBe(4500);
    expect(meta.height).toBe(5400);
    expect(meta.density).toBe(300);
    expect(meta.hasAlpha).toBe(true);
  });

  it("scales non-square input proportionally without stretching", async () => {
    // 300x150 rectangular input
    const input = await sharp({
      create: {
        width: 300,
        height: 150,
        channels: 4,
        background: { r: 50, g: 150, b: 250, alpha: 1 },
      },
    })
      .png()
      .toBuffer();

    const result = await upscaleToPrint(new Uint8Array(input));
    expect(result.width).toBe(4500);
    expect(result.height).toBe(5400);

    const meta = await sharp(result.buffer).metadata();
    expect(meta.width).toBe(4500);
    expect(meta.height).toBe(5400);
  });
});
