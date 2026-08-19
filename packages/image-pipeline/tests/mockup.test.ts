import { describe, expect, it } from "vitest";
import sharp from "sharp";
import {
  compositeCustomMockup,
  generateMockup,
  generateMugWrapCanvas,
  type MockupProductType,
} from "../src/mockup.js";
import { transparentSquare } from "./fixtures.js";

describe("mockup generator", () => {
  const products: MockupProductType[] = ["tshirt", "sweatshirt", "tote", "mug"];

  for (const product of products) {
    it(`generates a clean preview mockup for ${product}`, async () => {
      const artwork = await transparentSquare(500);
      const result = await generateMockup(new Uint8Array(artwork), {
        productType: product,
        outputSize: 600,
      });

      expect(result.productType).toBe(product);
      expect(result.width).toBe(600);
      expect(result.height).toBe(600);

      const meta = await sharp(result.buffer).metadata();
      expect(meta.format).toBe("png");
      expect(meta.width).toBe(600);
      expect(meta.height).toBe(600);
    });
  }

  describe("custom mockup template compositing", () => {
    it("composites artwork onto arbitrary custom template photo", async () => {
      const template = await sharp({
        create: {
          width: 1600,
          height: 1200,
          channels: 3,
          background: { r: 240, g: 235, b: 230 },
        },
      })
        .jpeg()
        .toBuffer();

      const artwork = await sharp({
        create: {
          width: 400,
          height: 500,
          channels: 4,
          background: { r: 50, g: 120, b: 220, alpha: 1 },
        },
      })
        .png()
        .toBuffer();

      const result = await compositeCustomMockup(
        new Uint8Array(artwork),
        new Uint8Array(template),
        {
          placement: {
            left_pct: 0.3,
            top_pct: 0.25,
            width_pct: 0.4,
            height_pct: 0.5,
            blend_mode: "multiply",
          },
          format: "jpeg",
        },
      );

      expect(result.width).toBe(1600);
      expect(result.height).toBe(1200);
      expect(result.format).toBe("jpeg");

      const meta = await sharp(result.buffer).metadata();
      expect(meta.format).toBe("jpeg");
      expect(meta.width).toBe(1600);
      expect(meta.height).toBe(1200);
    });

    it("supports all blend modes (over, overlay, soft-light, screen, darken, etc.)", async () => {
      const artwork = await sharp({
        create: {
          width: 200,
          height: 200,
          channels: 4,
          background: { r: 255, g: 255, b: 255, alpha: 1 },
        },
      })
        .png()
        .toBuffer();

      const template = await sharp({
        create: {
          width: 500,
          height: 500,
          channels: 4,
          background: { r: 100, g: 100, b: 100, alpha: 1 },
        },
      })
        .png()
        .toBuffer();

      for (const mode of ["over", "overlay", "soft-light", "screen", "darken", "lighten", "color-burn", "color-dodge"] as const) {
        const result = await compositeCustomMockup(
          new Uint8Array(artwork),
          new Uint8Array(template),
          {
            placement: {
              left_pct: 0.25,
              top_pct: 0.25,
              width_pct: 0.5,
              height_pct: 0.5,
              blend_mode: mode,
            },
            format: "png",
          },
        );

        expect(result.width).toBe(500);
        expect(result.height).toBe(500);
        expect(result.format).toBe("png");
      }
    });
  });

  describe("mug wrap canvas layout", () => {
    it("generates front-focused 2700x1050 wrap canvas with centered placement", async () => {
      // Known portrait design fixture (e.g. 4500x5400 aspect 5:6)
      const artwork = await sharp({
        create: {
          width: 500,
          height: 600,
          channels: 4,
          background: { r: 255, g: 0, b: 0, alpha: 1 },
        },
      })
        .png()
        .toBuffer();

      const result = await generateMugWrapCanvas(new Uint8Array(artwork), {
        layoutMode: "front_focus",
      });

      expect(result.width).toBe(2700);
      expect(result.height).toBe(1050);

      const meta = await sharp(result.buffer).metadata();
      expect(meta.format).toBe("png");
      expect(meta.width).toBe(2700);
      expect(meta.height).toBe(1050);

      // Verify geometry: Placement box is strictly centered at X: 1350, Y: 525
      const { left, top, width, height } = result.placementBox;
      const centerX = left + width / 2;
      const centerY = top + height / 2;

      expect(Math.abs(centerX - 1350)).toBeLessThanOrEqual(1.0);
      expect(Math.abs(centerY - 525)).toBeLessThanOrEqual(1.0);

      // Verify safe margins
      expect(left).toBeGreaterThanOrEqual(50);
      expect(top).toBeGreaterThanOrEqual(50);
      expect(left + width).toBeLessThanOrEqual(2700 - 50);
      expect(top + height).toBeLessThanOrEqual(1050 - 50);

      // Verify aspect ratio preserved (500/600 == 0.833)
      const aspect = width / height;
      expect(aspect).toBeCloseTo(500 / 600, 2);
    });

    it("supports dual-sided mug placement", async () => {
      const artwork = await transparentSquare(400);
      const result = await generateMugWrapCanvas(new Uint8Array(artwork), {
        layoutMode: "dual_sided",
      });

      expect(result.width).toBe(2700);
      expect(result.height).toBe(1050);
    });
  });
});

