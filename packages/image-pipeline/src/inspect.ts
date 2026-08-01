import { createHash } from "node:crypto";
import sharp from "sharp";
import type { Metadata } from "sharp";
import {
  DEFAULT_DECODE_LIMITS,
  ImageRejected,
  assertAllowedFormat,
  assertWithinByteLimit,
  assertWithinPixelLimits,
  type DecodeLimits,
} from "./limits.js";

/**
 * Everything we record about an asset before it is allowed into the pipeline.
 * Phase 1 only inspects; trimming, typography and mockups arrive in Phase 6.
 */
export interface ImageFacts {
  readonly format: string;
  readonly width: number;
  readonly height: number;
  readonly hasAlpha: boolean;
  /** True only when an alpha channel exists *and* some pixel is not fully opaque. */
  readonly hasTransparentPixels: boolean;
  readonly byteLength: number;
  readonly sha256: string;
}

export function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * Validate then describe an image buffer.
 *
 * Throws {@link ImageRejected} rather than returning a partial result: an asset
 * that fails a guard must never reach storage or a QA report.
 */
export async function inspectImage(
  bytes: Uint8Array,
  limits: DecodeLimits = DEFAULT_DECODE_LIMITS,
): Promise<ImageFacts> {
  assertWithinByteLimit(bytes.byteLength, limits);

  const pipeline = sharp(bytes, {
    limitInputPixels: limits.maxPixels,
    failOn: "error",
  });

  let metadata: Metadata;
  try {
    metadata = await pipeline.metadata();
  } catch (cause) {
    throw new ImageRejected(
      `Image could not be decoded: ${(cause as Error).message}`,
      "UNREADABLE",
    );
  }

  assertAllowedFormat(metadata.format);

  const width = metadata.width ?? 0;
  const height = metadata.height ?? 0;
  if (width === 0 || height === 0) {
    throw new ImageRejected("Image reports zero dimensions.", "UNREADABLE");
  }
  assertWithinPixelLimits(width, height, limits);

  const hasAlpha = metadata.hasAlpha === true;
  // `hasAlpha` only means a channel exists. A fully opaque alpha channel is a
  // common generator output and must not be reported as a transparent PNG.
  const minAlpha = hasAlpha ? await minimumAlpha(bytes, limits) : 255;

  return {
    format: metadata.format ?? "unknown",
    width,
    height,
    hasAlpha,
    hasTransparentPixels: hasAlpha && minAlpha < 255,
    byteLength: bytes.byteLength,
    sha256: sha256(bytes),
  };
}

/** Minimum alpha value across the image, read from Sharp's channel statistics. */
async function minimumAlpha(
  bytes: Uint8Array,
  limits: DecodeLimits,
): Promise<number> {
  const stats = await sharp(bytes, {
    limitInputPixels: limits.maxPixels,
  }).stats();
  const alpha = stats.channels.at(-1);
  return alpha?.min ?? 255;
}
