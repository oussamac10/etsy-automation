import sharp from "sharp";
import { inspectImage } from "./inspect.js";
import { DEFAULT_DECODE_LIMITS, type DecodeLimits } from "./limits.js";

export interface TrimOptions {
  /** Percentage of margin padding to add around trimmed content (e.g., 8 for 8%). Default: 8 */
  readonly marginPercent?: number | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface TrimResult {
  readonly buffer: Uint8Array;
  readonly originalWidth: number;
  readonly originalHeight: number;
  readonly trimmedWidth: number;
  readonly trimmedHeight: number;
  readonly paddedWidth: number;
  readonly paddedHeight: number;
}

/**
 * Identify visible foreground content bounds, extract without clipping edge anti-aliasing,
 * and add transparent margin padding.
 */
export async function trimAndPad(
  bytes: Uint8Array,
  options: TrimOptions = {},
): Promise<TrimResult> {
  const limits = options.limits ?? DEFAULT_DECODE_LIMITS;
  const marginPercent = options.marginPercent ?? 8;

  const facts = await inspectImage(bytes, limits);
  const bbox = facts.boundingBox;

  // If already at borders with no trim needed or empty content
  if (bbox.width <= 0 || bbox.height <= 0) {
    const rawBuffer = await sharp(bytes, { limitInputPixels: limits.maxPixels })
      .png()
      .toBuffer();
    return {
      buffer: new Uint8Array(rawBuffer),
      originalWidth: facts.width,
      originalHeight: facts.height,
      trimmedWidth: facts.width,
      trimmedHeight: facts.height,
      paddedWidth: facts.width,
      paddedHeight: facts.height,
    };
  }

  // 1. Extract content bounding box with a 1px safety border if within image bounds
  const safeLeft = Math.max(0, bbox.left - 1);
  const safeTop = Math.max(0, bbox.top - 1);
  const safeWidth = Math.min(facts.width - safeLeft, bbox.width + (bbox.left > 0 ? 1 : 0) + (bbox.left + bbox.width < facts.width ? 1 : 0));
  const safeHeight = Math.min(facts.height - safeTop, bbox.height + (bbox.top > 0 ? 1 : 0) + (bbox.top + bbox.height < facts.height ? 1 : 0));

  const extracted = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .extract({
      left: safeLeft,
      top: safeTop,
      width: safeWidth,
      height: safeHeight,
    })
    .png()
    .toBuffer();

  // 2. Compute margin padding
  const padX = Math.max(8, Math.round(safeWidth * (marginPercent / 100)));
  const padY = Math.max(8, Math.round(safeHeight * (marginPercent / 100)));
  const paddedWidth = safeWidth + padX * 2;
  const paddedHeight = safeHeight + padY * 2;

  // 3. Extend with transparent padding
  const resultBuffer = await sharp(extracted, { limitInputPixels: limits.maxPixels })
    .extend({
      top: padY,
      bottom: padY,
      left: padX,
      right: padX,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();

  return {
    buffer: new Uint8Array(resultBuffer),
    originalWidth: facts.width,
    originalHeight: facts.height,
    trimmedWidth: safeWidth,
    trimmedHeight: safeHeight,
    paddedWidth,
    paddedHeight,
  };
}
