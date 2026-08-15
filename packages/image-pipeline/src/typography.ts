import sharp from "sharp";
import { DEFAULT_DECODE_LIMITS, type DecodeLimits } from "./limits.js";

export type TypographyLayout = "centered" | "stacked" | "arched" | "top" | "bottom";

export interface TypographyOptions {
  readonly slogan: string;
  readonly layout?: TypographyLayout | undefined;
  readonly fontFamily?: string | undefined;
  readonly fill?: string | undefined;
  readonly stroke?: string | undefined;
  readonly strokeWidth?: number | undefined;
  readonly fontSize?: number | undefined;
  readonly canvasWidth?: number | undefined;
  readonly canvasHeight?: number | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface TypographyResult {
  readonly buffer: Uint8Array;
  readonly sloganRendered: string;
  readonly layout: TypographyLayout;
  readonly fontFamily: string;
  readonly fill: string;
  readonly svgOverlay: string;
}

/** Standard, safe local font families */
export const ALLOWED_FONTS = [
  "Arial, Helvetica, sans-serif",
  "Impact, sans-serif",
  "Trebuchet MS, sans-serif",
  "Montserrat, Arial, sans-serif",
  "Georgia, serif",
  "Courier New, monospace",
] as const;

function escapeXml(unsafe: string): string {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Determine layout from instructions or fallback to stacked
 */
export function parseTypographyLayout(instructions?: string | null): TypographyLayout {
  if (!instructions) return "stacked";
  const lower = instructions.toLowerCase();
  if (lower.includes("arch") || lower.includes("curv")) return "arched";
  if (lower.includes("top") || lower.includes("above")) return "top";
  if (lower.includes("bottom") || lower.includes("below")) return "bottom";
  if (lower.includes("center")) return "centered";
  return "stacked";
}

/**
 * Generate SVG text overlay for the given layout and dimensions.
 */
export function generateTypographySvg(options: TypographyOptions): { svg: string; layout: TypographyLayout; fontFamily: string; fill: string } {
  const width = options.canvasWidth ?? 4500;
  const height = options.canvasHeight ?? 5400;
  const layout = options.layout ?? "stacked";
  const fontFamily = options.fontFamily ?? "Impact, Arial, sans-serif";
  const fill = options.fill ?? "#18181B";
  const stroke = options.stroke ? `stroke="${escapeXml(options.stroke)}" stroke-width="${options.strokeWidth ?? 8}"` : "";

  const escapedSlogan = escapeXml(options.slogan.trim());

  let textSvg = "";

  if (layout === "arched") {
    const fontSize = options.fontSize ?? Math.min(280, Math.round(width / Math.max(8, escapedSlogan.length * 0.8)));
    const pathD = `M ${Math.round(width * 0.1)} ${Math.round(height * 0.22)} A ${Math.round(width * 0.55)} ${Math.round(height * 0.35)} 0 0 1 ${Math.round(width * 0.9)} ${Math.round(height * 0.22)}`;
    textSvg = `
      <defs>
        <path id="archPath" d="${pathD}" fill="none" />
      </defs>
      <text font-family="${escapeXml(fontFamily)}" font-size="${fontSize}px" font-weight="900" fill="${escapeXml(fill)}" ${stroke} letter-spacing="4px">
        <textPath href="#archPath" startOffset="50%" text-anchor="middle">
          ${escapedSlogan}
        </textPath>
      </text>
    `;
  } else if (layout === "top") {
    const fontSize = options.fontSize ?? Math.min(260, Math.round(width / Math.max(8, escapedSlogan.length * 0.75)));
    textSvg = `
      <text x="50%" y="${Math.round(height * 0.12)}" text-anchor="middle" font-family="${escapeXml(fontFamily)}" font-size="${fontSize}px" font-weight="900" fill="${escapeXml(fill)}" ${stroke} letter-spacing="3px">
        ${escapedSlogan}
      </text>
    `;
  } else if (layout === "bottom") {
    const fontSize = options.fontSize ?? Math.min(260, Math.round(width / Math.max(8, escapedSlogan.length * 0.75)));
    textSvg = `
      <text x="50%" y="${Math.round(height * 0.90)}" text-anchor="middle" font-family="${escapeXml(fontFamily)}" font-size="${fontSize}px" font-weight="900" fill="${escapeXml(fill)}" ${stroke} letter-spacing="3px">
        ${escapedSlogan}
      </text>
    `;
  } else if (layout === "stacked") {
    // Break slogan into 2-3 word lines
    const words = escapedSlogan.split(/\s+/);
    const lines: string[] = [];
    let currentLine = "";

    for (const word of words) {
      if ((currentLine + " " + word).trim().length <= 18) {
        currentLine = (currentLine + " " + word).trim();
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);

    const maxLineLen = Math.max(...lines.map((l) => l.length), 6);
    const fontSize = options.fontSize ?? Math.min(300, Math.round(width / (maxLineLen * 0.75)));
    const lineHeight = Math.round(fontSize * 1.18);
    const startY = Math.round(height * 0.84 - (lines.length - 1) * lineHeight * 0.5);

    const tspans = lines
      .map(
        (line, idx) =>
          `<tspan x="50%" y="${startY + idx * lineHeight}">${line}</tspan>`,
      )
      .join("\n");

    textSvg = `
      <text text-anchor="middle" font-family="${escapeXml(fontFamily)}" font-size="${fontSize}px" font-weight="900" fill="${escapeXml(fill)}" ${stroke} letter-spacing="2px">
        ${tspans}
      </text>
    `;
  } else {
    // Centered
    const fontSize = options.fontSize ?? Math.min(280, Math.round(width / Math.max(8, escapedSlogan.length * 0.75)));
    textSvg = `
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="${escapeXml(fontFamily)}" font-size="${fontSize}px" font-weight="900" fill="${escapeXml(fill)}" ${stroke} letter-spacing="2px">
        ${escapedSlogan}
      </text>
    `;
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    ${textSvg}
  </svg>`;

  return { svg, layout, fontFamily, fill };
}

/**
 * Composite deterministic SVG typography onto an artwork canvas.
 */
export async function compositeTypography(
  artworkBytes: Uint8Array,
  options: TypographyOptions,
): Promise<TypographyResult> {
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    maxPixels: 60_000_000,
  };

  const metadata = await sharp(artworkBytes, { limitInputPixels: limits.maxPixels }).metadata();
  const width = metadata.width ?? options.canvasWidth ?? 4500;
  const height = metadata.height ?? options.canvasHeight ?? 5400;

  const { svg, layout, fontFamily, fill } = generateTypographySvg({
    ...options,
    canvasWidth: width,
    canvasHeight: height,
  });

  const svgBuffer = Buffer.from(svg);

  const resultBuffer = await sharp(artworkBytes, { limitInputPixels: limits.maxPixels })
    .composite([
      {
        input: svgBuffer,
        top: 0,
        left: 0,
      },
    ])
    .png()
    .toBuffer();

  return {
    buffer: new Uint8Array(resultBuffer),
    sloganRendered: options.slogan,
    layout,
    fontFamily,
    fill,
    svgOverlay: svg,
  };
}
