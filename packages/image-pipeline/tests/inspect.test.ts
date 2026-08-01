import { describe, expect, it } from "vitest";
import { ImageRejected, inspectImage, sha256 } from "../src/index.js";
import {
  jpegSquare,
  opaqueAlphaSquare,
  opaqueSquare,
  transparentSquare,
} from "./fixtures.js";

describe("inspectImage", () => {
  it("describes an opaque PNG", async () => {
    const facts = await inspectImage(await opaqueSquare(32));
    expect(facts.format).toBe("png");
    expect(facts.width).toBe(32);
    expect(facts.height).toBe(32);
    expect(facts.hasTransparentPixels).toBe(false);
  });

  it("does not report an all-opaque alpha channel as transparent", async () => {
    const facts = await inspectImage(await opaqueAlphaSquare());
    expect(facts.hasAlpha).toBe(true);
    expect(facts.hasTransparentPixels).toBe(false);
  });

  it("detects genuine transparency", async () => {
    const facts = await inspectImage(await transparentSquare());
    expect(facts.hasAlpha).toBe(true);
    expect(facts.hasTransparentPixels).toBe(true);
  });

  it("accepts JPEG input", async () => {
    const facts = await inspectImage(await jpegSquare());
    expect(facts.format).toBe("jpeg");
  });

  it("records a stable content hash", async () => {
    const bytes = await opaqueSquare(16);
    const facts = await inspectImage(bytes);
    expect(facts.sha256).toBe(sha256(bytes));
    expect(facts.sha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("rejects a payload above the byte limit before decoding", async () => {
    const bytes = await opaqueSquare(16);
    await expect(
      inspectImage(bytes, {
        maxBytes: 8,
        maxPixels: 1_000_000,
        maxWidth: 1000,
        maxHeight: 1000,
      }),
    ).rejects.toMatchObject({ code: "TOO_LARGE" });
  });

  it("rejects an image above the pixel limit", async () => {
    const bytes = await opaqueSquare(64);
    await expect(
      inspectImage(bytes, {
        maxBytes: 10_000_000,
        maxPixels: 10_000_000,
        maxWidth: 32,
        maxHeight: 32,
      }),
    ).rejects.toMatchObject({ code: "TOO_MANY_PIXELS" });
  });

  it("rejects bytes that are not an image", async () => {
    const bytes = new TextEncoder().encode("<svg onload='alert(1)'/>");
    await expect(inspectImage(bytes)).rejects.toBeInstanceOf(ImageRejected);
  });
});
