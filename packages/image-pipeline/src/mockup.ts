import sharp, { type Blend, type OverlayOptions } from "sharp";
import { DEFAULT_DECODE_LIMITS, type DecodeLimits } from "./limits.js";

export type MockupProductType = "tshirt" | "sweatshirt" | "tote" | "mug";

export function normalizeProductType(product: string): MockupProductType {
  const p = product.toLowerCase();
  if (p.includes("shirt") || p.includes("tee") || p.includes("apparel") || p.includes("top") || p.includes("cloth")) {
    return "tshirt";
  }
  if (p.includes("hoodie") || p.includes("sweat") || p.includes("jacket") || p.includes("fleece") || p.includes("jumper")) {
    return "sweatshirt";
  }
  if (p.includes("mug") || p.includes("cup") || p.includes("drink") || p.includes("tumbler") || p.includes("ceramic")) {
    return "mug";
  }
  return "tote";
}

export interface MockupOptions {
  readonly productType: MockupProductType;
  readonly garmentColor?: "white" | "black" | "heather_gray" | "natural" | undefined;
  readonly outputSize?: number | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface MockupResult {
  readonly buffer: Uint8Array;
  readonly productType: MockupProductType;
  readonly width: number;
  readonly height: number;
}

interface ProductTemplateSpec {
  readonly svgBackground: string;
  readonly placement: {
    readonly left: number;
    readonly top: number;
    readonly width: number;
    readonly height: number;
  };
}

function getProductTemplate(product: MockupProductType, size: number, color: string): ProductTemplateSpec {
  const isDark = color === "black";
  const garmentFill = color === "black" ? "#18181B" : color === "heather_gray" ? "#E4E4E7" : color === "natural" ? "#F4F4F5" : "#FFFFFF";
  const strokeColor = isDark ? "#27272A" : "#D4D4D8";
  const shadowColor = "rgba(0,0,0,0.08)";

  if (product === "tshirt") {
    const svg = `
      <svg width="${size}" height="${size}" viewBox="0 0 1200 1200" xmlns="http://www.w3.org/2000/svg">
        <rect width="1200" height="1200" fill="#FAFAFA" />
        <!-- T-Shirt Body -->
        <g transform="translate(100, 100)">
          <!-- Drop Shadow -->
          <path d="M 320 80 Q 500 130 680 80 L 860 220 L 740 380 L 670 330 L 670 940 Q 500 970 330 940 L 330 330 L 260 380 L 140 220 Z" fill="${shadowColor}" transform="translate(12, 16)" />
          <!-- Main Garment -->
          <path d="M 320 80 Q 500 130 680 80 L 860 220 L 740 380 L 670 330 L 670 940 Q 500 970 330 940 L 330 330 L 260 380 L 140 220 Z" fill="${garmentFill}" stroke="${strokeColor}" stroke-width="4" stroke-linejoin="round" />
          <!-- Collar Curve -->
          <path d="M 380 80 Q 500 180 620 80 Q 500 150 380 80" fill="#E4E4E7" stroke="${strokeColor}" stroke-width="3" />
          <!-- Sleeve Folds -->
          <line x1="260" y1="380" x2="330" y2="330" stroke="${strokeColor}" stroke-width="3" />
          <line x1="740" y1="380" x2="670" y2="330" stroke="${strokeColor}" stroke-width="3" />
        </g>
      </svg>
    `;
    return {
      svgBackground: svg,
      placement: { left: Math.round(size * 0.35), top: Math.round(size * 0.32), width: Math.round(size * 0.30), height: Math.round(size * 0.36) },
    };
  }

  if (product === "sweatshirt") {
    const svg = `
      <svg width="${size}" height="${size}" viewBox="0 0 1200 1200" xmlns="http://www.w3.org/2000/svg">
        <rect width="1200" height="1200" fill="#FAFAFA" />
        <g transform="translate(100, 80)">
          <!-- Drop Shadow -->
          <path d="M 300 100 Q 500 140 700 100 L 920 280 L 780 440 L 700 390 L 700 960 Q 500 990 300 960 L 300 390 L 220 440 L 80 280 Z" fill="${shadowColor}" transform="translate(12, 16)" />
          <!-- Sweatshirt Body -->
          <path d="M 300 100 Q 500 140 700 100 L 920 280 L 780 440 L 700 390 L 700 960 Q 500 990 300 960 L 300 390 L 220 440 L 80 280 Z" fill="${garmentFill}" stroke="${strokeColor}" stroke-width="4" />
          <!-- Ribbed Collar & Hem -->
          <path d="M 360 100 Q 500 200 640 100 Q 500 160 360 100" fill="#D4D4D8" stroke="${strokeColor}" stroke-width="3" />
          <rect x="300" y="930" width="400" height="40" fill="#D4D4D8" stroke="${strokeColor}" stroke-width="2" rx="4" />
        </g>
      </svg>
    `;
    return {
      svgBackground: svg,
      placement: { left: Math.round(size * 0.35), top: Math.round(size * 0.33), width: Math.round(size * 0.30), height: Math.round(size * 0.36) },
    };
  }

  if (product === "tote") {
    const svg = `
      <svg width="${size}" height="${size}" viewBox="0 0 1200 1200" xmlns="http://www.w3.org/2000/svg">
        <rect width="1200" height="1200" fill="#FAFAFA" />
        <g transform="translate(150, 100)">
          <!-- Handles -->
          <path d="M 320 420 Q 320 100 450 100 Q 580 100 580 420" fill="none" stroke="#D4D4D8" stroke-width="28" stroke-linecap="round" />
          <!-- Tote Bag Body -->
          <rect x="200" y="420" width="500" height="580" rx="20" fill="${garmentFill}" stroke="${strokeColor}" stroke-width="4" />
          <line x1="200" y1="460" x2="700" y2="460" stroke="${strokeColor}" stroke-width="2" stroke-dasharray="8 6" />
        </g>
      </svg>
    `;
    return {
      svgBackground: svg,
      placement: { left: Math.round(size * 0.32), top: Math.round(size * 0.46), width: Math.round(size * 0.36), height: Math.round(size * 0.38) },
    };
  }

  // Mug
  const svg = `
    <svg width="${size}" height="${size}" viewBox="0 0 1200 1200" xmlns="http://www.w3.org/2000/svg">
      <rect width="1200" height="1200" fill="#FAFAFA" />
      <g transform="translate(250, 200)">
        <!-- Handle -->
        <path d="M 520 220 C 720 220 720 540 520 540" fill="none" stroke="#E4E4E7" stroke-width="46" stroke-linecap="round" />
        <!-- Cylinder Body (Canvas X: 400..800, Center: 600) -->
        <rect x="150" y="160" width="400" height="520" rx="30" fill="#FFFFFF" stroke="#D4D4D8" stroke-width="4" />
        <!-- Gloss Highlights -->
        <path d="M 180 180 L 180 650" stroke="rgba(255,255,255,0.8)" stroke-width="16" stroke-linecap="round" />
      </g>
    </svg>
  `;
  return {
    svgBackground: svg,
    placement: {
      left: Math.round(size * 0.37),
      top: Math.round(size * 0.36),
      width: Math.round(size * 0.26),
      height: Math.round(size * 0.32),
    },
  };
}

/**
 * Render deterministic product preview mockup with composited artwork.
 */
export async function generateMockup(
  artworkBytes: Uint8Array,
  options: MockupOptions,
): Promise<MockupResult> {
  const size = options.outputSize ?? 1200;
  const color = options.garmentColor ?? "white";
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    maxPixels: 60_000_000,
  };

  const template = getProductTemplate(options.productType, size, color);

  // Resize artwork to fit the product's placement bounding box
  const resizedArtwork = await sharp(artworkBytes, { limitInputPixels: limits.maxPixels })
    .resize({
      width: template.placement.width,
      height: template.placement.height,
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();

  const backgroundBuffer = Buffer.from(template.svgBackground);

  const mockupBuffer = await sharp(backgroundBuffer, { limitInputPixels: limits.maxPixels })
    .composite([
      {
        input: resizedArtwork,
        left: template.placement.left,
        top: template.placement.top,
      },
    ])
    .png({ compressionLevel: 7 })
    .toBuffer();

  return {
    buffer: new Uint8Array(mockupBuffer),
    productType: options.productType,
    width: size,
    height: size,
  };
}

export interface MugWrapOptions {
  readonly canvasWidth?: number | undefined;
  readonly canvasHeight?: number | undefined;
  readonly layoutMode?: "front_focus" | "dual_sided" | "full_wrap" | undefined;
  readonly safeMarginPx?: number | undefined;
  readonly scale?: number | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface MugWrapResult {
  readonly buffer: Uint8Array;
  readonly width: number;
  readonly height: number;
  readonly placementBox: {
    readonly left: number;
    readonly top: number;
    readonly width: number;
    readonly height: number;
  };
}

/**
 * Generate a provider-specific 2700x1050 wrap canvas with artwork placed
 * squarely in the camera-facing front-visible region with safe margins.
 */
export async function generateMugWrapCanvas(
  artworkBytes: Uint8Array,
  options: MugWrapOptions = {},
): Promise<MugWrapResult> {
  const canvasWidth = options.canvasWidth ?? 2700;
  const canvasHeight = options.canvasHeight ?? 1050;
  const layoutMode = options.layoutMode ?? "front_focus";
  const scale = options.scale ?? 0.88;
  const safeMargin = options.safeMarginPx ?? 50;
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    maxPixels: 60_000_000,
  };

  const targetMaxHeight = Math.round((canvasHeight - safeMargin * 2) * scale);
  const targetMaxWidth = 850;

  const resizedArtwork = await sharp(artworkBytes, { limitInputPixels: limits.maxPixels })
    .resize({
      width: targetMaxWidth,
      height: targetMaxHeight,
      fit: "inside",
      withoutEnlargement: false,
    })
    .png()
    .toBuffer();

  const meta = await sharp(resizedArtwork).metadata();
  const artW = meta.width ?? targetMaxWidth;
  const artH = meta.height ?? targetMaxHeight;

  // Front camera-facing center is X: 1350, Y: 525 on the 2700x1050 wrap
  const left = Math.round((canvasWidth - artW) / 2);
  const top = Math.round((canvasHeight - artH) / 2);

  const composites: Array<{ input: Buffer; left: number; top: number }> = [];

  if (layoutMode === "dual_sided") {
    const leftSideLeft = Math.round(675 - artW / 2);
    const rightSideLeft = Math.round(2025 - artW / 2);
    composites.push(
      { input: resizedArtwork, left: Math.max(safeMargin, leftSideLeft), top },
      { input: resizedArtwork, left: Math.min(canvasWidth - artW - safeMargin, rightSideLeft), top },
    );
  } else {
    // Default "front_focus"
    composites.push({ input: resizedArtwork, left, top });
  }

  const canvasBuffer = await sharp({
    create: {
      width: canvasWidth,
      height: canvasHeight,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite(composites)
    .png({ compressionLevel: 7 })
    .toBuffer();

  return {
    buffer: new Uint8Array(canvasBuffer),
    width: canvasWidth,
    height: canvasHeight,
    placementBox: { left, top, width: artW, height: artH },
  };
}

export interface CustomMockupPlacement {
  readonly id?: string | undefined;
  /** Horizontal position of top-left corner as a percentage (0.0 to 1.0) of template width. Default 0.25 */
  readonly left_pct?: number | undefined;
  /** Vertical position of top-left corner as a percentage (0.0 to 1.0) of template height. Default 0.25 */
  readonly top_pct?: number | undefined;
  /** Maximum width of artwork bounding box as a percentage (0.0 to 1.0) of template width. Default 0.50 */
  readonly width_pct?: number | undefined;
  /** Maximum height of artwork bounding box as a percentage (0.0 to 1.0) of template height. Default 0.50 */
  readonly height_pct?: number | undefined;
  /** Blend mode for realistic texture simulation. Default 'over' or 'multiply' */
  readonly blend_mode?: MockupBlendMode | string | undefined;
  /** Optional rotation in degrees (-180 to 180). Default 0 */
  readonly angle_deg?: number | undefined;
  /** Optional artwork identifier or variant key */
  readonly artwork_source_id?: string | undefined;
}

export type MockupBlendMode =
  | "over"
  | "multiply"
  | "screen"
  | "overlay"
  | "soft-light"
  | "hard-light"
  | "darken"
  | "lighten"
  | "color-burn"
  | "color-dodge";

export function resolveSharpBlendMode(mode: MockupBlendMode | string | undefined): Blend {
  const norm = (mode || "over").toLowerCase().trim().replace(/_/g, "-");
  switch (norm) {
    case "multiply":
      return "multiply";
    case "screen":
      return "screen";
    case "overlay":
      return "overlay";
    case "soft-light":
      return "soft-light";
    case "hard-light":
      return "hard-light";
    case "darken":
      return "darken";
    case "lighten":
      return "lighten";
    case "color-burn":
    case "colour-burn":
      return "colour-burn";
    case "color-dodge":
    case "colour-dodge":
      return "colour-dodge";
    case "over":
    default:
      return "over";
  }
}

export interface CustomMockupResult {
  readonly buffer: Uint8Array;
  readonly width: number;
  readonly height: number;
  readonly format: "jpeg" | "png";
}

/**
 * Composite artwork PNG onto an arbitrary custom mockup template image (e.g. lifestyle photo, flat-lay, sticker sheets).
 * Supports single placement or multiple placement zones on a single template.
 */
export async function compositeCustomMockup(
  artworkBytes: Uint8Array,
  templateBytes: Uint8Array,
  options: {
    readonly placement?: CustomMockupPlacement | undefined;
    readonly placements?: readonly CustomMockupPlacement[] | undefined;
    readonly limits?: DecodeLimits | undefined;
    readonly format?: "jpeg" | "png" | undefined;
    readonly quality?: number | undefined;
  } = {},
): Promise<CustomMockupResult> {
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    maxPixels: 60_000_000,
  };
  const format = options.format ?? "jpeg";
  const quality = options.quality ?? 90;

  // Collect placement list (supports both legacy single placement and multi-placement array)
  const placementList: CustomMockupPlacement[] =
    options.placements && options.placements.length > 0
      ? [...options.placements]
      : [options.placement ?? {}];

  // 1. Get template image metadata
  const templateMeta = await sharp(templateBytes, { limitInputPixels: limits.maxPixels }).metadata();
  const templateWidth = templateMeta.width ?? 1200;
  const templateHeight = templateMeta.height ?? 1200;

  // 2. Build composite layers for each placement zone
  const compositeLayers: OverlayOptions[] = [];

  for (const placement of placementList) {
    const leftPct = Math.max(0, Math.min(0.95, placement.left_pct ?? 0.25));
    const topPct = Math.max(0, Math.min(0.95, placement.top_pct ?? 0.25));
    const widthPct = Math.max(0.05, Math.min(1.0 - leftPct, placement.width_pct ?? 0.50));
    const heightPct = Math.max(0.05, Math.min(1.0 - topPct, placement.height_pct ?? 0.50));

    const targetBoxWidth = Math.max(10, Math.round(templateWidth * widthPct));
    const targetBoxHeight = Math.max(10, Math.round(templateHeight * heightPct));
    const targetLeft = Math.round(templateWidth * leftPct);
    const targetTop = Math.round(templateHeight * topPct);

    let artworkPipeline = sharp(artworkBytes, { limitInputPixels: limits.maxPixels })
      .toColorspace("srgb")
      .resize({
        width: targetBoxWidth,
        height: targetBoxHeight,
        fit: "inside",
        withoutEnlargement: false,
      });

    if (placement.angle_deg && Math.abs(placement.angle_deg) > 0.01) {
      artworkPipeline = artworkPipeline.rotate(placement.angle_deg, {
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      });
    }

    const resizedArtworkBuffer = await artworkPipeline.png().toBuffer();
    const resizedMeta = await sharp(resizedArtworkBuffer).metadata();
    const actualArtW = resizedMeta.width ?? targetBoxWidth;
    const actualArtH = resizedMeta.height ?? targetBoxHeight;

    const compositeLeft = Math.round(targetLeft + (targetBoxWidth - actualArtW) / 2);
    const compositeTop = Math.round(targetTop + (targetBoxHeight - actualArtH) / 2);
    const blendMode = resolveSharpBlendMode(placement.blend_mode);

    compositeLayers.push({
      input: resizedArtworkBuffer,
      left: compositeLeft,
      top: compositeTop,
      blend: blendMode,
    });
  }

  // 3. Composite all layers onto template in a single pass with matching sRGB colorspace
  const finalPipeline = sharp(templateBytes, { limitInputPixels: limits.maxPixels })
    .toColorspace("srgb")
    .composite(compositeLayers);

  let outputBuffer: Buffer;
  if (format === "png") {
    outputBuffer = await finalPipeline.png({ compressionLevel: 7 }).toBuffer();
  } else {
    outputBuffer = await finalPipeline.jpeg({ quality, mozjpeg: true }).toBuffer();
  }

  return {
    buffer: new Uint8Array(outputBuffer),
    width: templateWidth,
    height: templateHeight,
    format,
  };
}


