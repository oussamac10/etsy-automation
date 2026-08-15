import { describe, expect, it } from "vitest";
import sharp from "sharp";
import {
  compositeTypography,
  generateTypographySvg,
  parseTypographyLayout,
} from "../src/typography.js";
import { transparentSquare } from "./fixtures.js";

describe("typography engine", () => {
  it("parses layout from natural language instructions", () => {
    expect(parseTypographyLayout("Arched above the artwork in bold")).toBe("arched");
    expect(parseTypographyLayout("Curved lettering along the top")).toBe("arched");
    expect(parseTypographyLayout("Placed top of the graphic")).toBe("top");
    expect(parseTypographyLayout("Bottom text line")).toBe("bottom");
    expect(parseTypographyLayout("Centered slogan")).toBe("centered");
    expect(parseTypographyLayout(null)).toBe("stacked");
  });

  it("generates valid SVG for stacked layout with exact slogan", () => {
    const { svg, layout } = generateTypographySvg({
      slogan: "Coffee First Then Coding",
      layout: "stacked",
    });
    expect(layout).toBe("stacked");
    expect(svg).toContain("Coffee First");
    expect(svg).toContain("Coding");
  });

  it("generates valid SVG for arched layout with exact slogan", () => {
    const { svg, layout } = generateTypographySvg({
      slogan: "Never Stop Learning",
      layout: "arched",
    });
    expect(layout).toBe("arched");
    expect(svg).toContain("textPath");
    expect(svg).toContain("Never Stop Learning");
  });

  it("composites slogan overlay onto artwork buffer", async () => {
    const base = await transparentSquare(1000);
    const result = await compositeTypography(new Uint8Array(base), {
      slogan: "Stay Curious",
      layout: "stacked",
    });

    expect(result.sloganRendered).toBe("Stay Curious");
    expect(result.buffer).toBeInstanceOf(Uint8Array);

    const meta = await sharp(result.buffer).metadata();
    expect(meta.width).toBe(1000);
    expect(meta.height).toBe(1000);
  });
});
