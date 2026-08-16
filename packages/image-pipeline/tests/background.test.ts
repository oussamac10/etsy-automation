import { describe, expect, it } from "vitest";
import sharp from "sharp";
import {
  detectEdgeBackground,
  ensureTransparentBackground,
  removeEdgeConnectedBackground,
} from "../src/background.js";
import { inspectImage } from "../src/inspect.js";

/**
 * Creates a synthetic 128x128 image with:
 * - Solid near-white canvas background (254, 254, 254)
 * - Centered brown book / mug rectangle (from x=32..96, y=32..96, color: 120, 60, 30)
 * - Interior white detail (from x=48..72, y=48..72, color: 255, 255, 255)
 */
async function createSyntheticArtworkWithInteriorWhite(
  size = 128,
  bgR = 254,
  bgG = 254,
  bgB = 254,
): Promise<Uint8Array> {
  const channels = 4;
  const buffer = new Uint8Array(size * size * channels);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * channels;

      // Interior white element (e.g. book pages / coffee cup steam)
      if (x >= 48 && x <= 80 && y >= 48 && y <= 80) {
        buffer[idx] = 255;
        buffer[idx + 1] = 255;
        buffer[idx + 2] = 255;
        buffer[idx + 3] = 255;
      }
      // Artwork subject (e.g. brown book cover / mug)
      else if (x >= 28 && x <= 100 && y >= 28 && y <= 100) {
        buffer[idx] = 130;
        buffer[idx + 1] = 65;
        buffer[idx + 2] = 30;
        buffer[idx + 3] = 255;
      }
      // Outer canvas background
      else {
        buffer[idx] = bgR;
        buffer[idx + 1] = bgG;
        buffer[idx + 2] = bgB;
        buffer[idx + 3] = 255;
      }
    }
  }

  const png = await sharp(buffer, { raw: { width: size, height: size, channels } })
    .png()
    .toBuffer();

  return new Uint8Array(png);
}

describe("background detection and removal", () => {
  it("detects edge-connected near-white background", async () => {
    const img = await createSyntheticArtworkWithInteriorWhite(128, 252, 252, 252);
    const detection = await detectEdgeBackground(img);

    expect(detection.detected).toBe(true);
    expect(detection.isOpaqueNearWhite).toBe(true);
    expect(detection.isAlreadyTransparent).toBe(false);
    expect(detection.cornersNearWhiteCount).toBe(4);
    expect(detection.backgroundColor.r).toBeGreaterThanOrEqual(250);
  });

  it("removes edge-connected white background while strictly preserving interior white details", async () => {
    const size = 128;
    const img = await createSyntheticArtworkWithInteriorWhite(size, 254, 254, 254);

    const result = await removeEdgeConnectedBackground(img);
    expect(result.modified).toBe(true);
    expect(result.removedPixelCount).toBeGreaterThan(0);

    const { data } = await sharp(result.buffer)
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });

    // 1. Check outer corners (should be alpha 0)
    const cornerOffsets = [
      (0 * size + 0) * 4,
      (0 * size + (size - 1)) * 4,
      ((size - 1) * size + 0) * 4,
      ((size - 1) * size + (size - 1)) * 4,
    ];
    for (const offset of cornerOffsets) {
      expect(data[offset + 3]).toBe(0);
    }

    // 2. Check artwork subject (x=30, y=30) -> fully opaque brown
    const subjectOffset = (30 * size + 30) * 4;
    expect(data[subjectOffset + 3]).toBe(255);
    expect(data[subjectOffset]).toBe(130);
    expect(data[subjectOffset + 1]).toBe(65);
    expect(data[subjectOffset + 2]).toBe(30);

    // 3. Check interior white detail (x=64, y=64) -> STRICTLY preserved, fully opaque white
    const interiorOffset = (64 * size + 64) * 4;
    expect(data[interiorOffset + 3]).toBe(255); // Alpha preserved!
    expect(data[interiorOffset]).toBe(255);
    expect(data[interiorOffset + 1]).toBe(255);
    expect(data[interiorOffset + 2]).toBe(255);
  });

  it("composites onto dark background without white rectangular frame", async () => {
    const size = 128;
    const img = await createSyntheticArtworkWithInteriorWhite(size, 255, 255, 255);
    const cleaned = await ensureTransparentBackground(img);

    // Composite cleaned artwork over solid black canvas (simulating black T-shirt mockup)
    const blackCanvas = await sharp({
      create: {
        width: size,
        height: size,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 1 },
      },
    })
      .composite([{ input: Buffer.from(cleaned.buffer), top: 0, left: 0 }])
      .png()
      .toBuffer();

    const { data } = await sharp(blackCanvas).raw().toBuffer({ resolveWithObject: true });

    // Outer corner must be pure black (0,0,0), NOT white (255,255,255)
    const cornerOffset = (0 * size + 0) * 4;
    expect(data[cornerOffset]).toBe(0);
    expect(data[cornerOffset + 1]).toBe(0);
    expect(data[cornerOffset + 2]).toBe(0);

    // Center interior detail remains white (255,255,255)
    const centerOffset = (64 * size + 64) * 4;
    expect(data[centerOffset]).toBe(255);
    expect(data[centerOffset + 1]).toBe(255);
    expect(data[centerOffset + 2]).toBe(255);
  });

  it("preserves already transparent PNG without modifying transparent pixels", async () => {
    const transparentImg = await sharp({
      create: {
        width: 64,
        height: 64,
        channels: 4,
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      },
    })
      .composite([
        {
          input: await sharp({
            create: {
              width: 32,
              height: 32,
              channels: 4,
              background: { r: 255, g: 100, b: 50, alpha: 1 },
            },
          })
            .png()
            .toBuffer(),
          top: 16,
          left: 16,
        },
      ])
      .png()
      .toBuffer();

    const result = await ensureTransparentBackground(new Uint8Array(transparentImg));
    expect(result.detection.isAlreadyTransparent).toBe(true);

    const facts = await inspectImage(result.buffer);
    expect(facts.hasAlpha).toBe(true);
    expect(facts.hasTransparentPixels).toBe(true);
  });

  it("does not blindly remove non-white solid backgrounds", async () => {
    const darkBlueSquare = await sharp({
      create: {
        width: 64,
        height: 64,
        channels: 3,
        background: { r: 10, g: 20, b: 80 },
      },
    })
      .png()
      .toBuffer();

    const detection = await detectEdgeBackground(new Uint8Array(darkBlueSquare));
    expect(detection.detected).toBe(false);
    expect(detection.isOpaqueNearWhite).toBe(false);
  });
});
