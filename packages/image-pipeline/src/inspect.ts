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

export interface BoundingBox {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

export interface EdgeMargins {
  readonly top: number;
  readonly bottom: number;
  readonly left: number;
  readonly right: number;
}

/**
 * Everything we record about an asset before and after pipeline processing.
 */
export interface ImageFacts {
  readonly format: string;
  readonly width: number;
  readonly height: number;
  readonly hasAlpha: boolean;
  /** True only when an alpha channel exists *and* some pixel is not fully opaque. */
  readonly hasTransparentPixels: boolean;
  readonly transparentPixelRatio: number;
  readonly boundingBox: BoundingBox;
  readonly edgeMargins: EdgeMargins;
  readonly colorSpace: string;
  readonly densityDpi: number;
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

  const { data, info } = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  let minX = info.width;
  let minY = info.height;
  let maxX = -1;
  let maxY = -1;
  let transparentCount = 0;
  let minAlpha = 255;
  const totalPixels = info.width * info.height;

  for (let y = 0; y < info.height; y++) {
    const rowOffset = y * info.width * 4;
    for (let x = 0; x < info.width; x++) {
      const alpha = data[rowOffset + x * 4 + 3] ?? 255;
      if (alpha < minAlpha) {
        minAlpha = alpha;
      }
      if (alpha < 128) {
        transparentCount++;
      }
      if (alpha > 10) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }

  const hasContent = maxX >= minX && maxY >= minY;
  const boundingBox: BoundingBox = hasContent
    ? { left: minX, top: minY, width: maxX - minX + 1, height: maxY - minY + 1 }
    : { left: 0, top: 0, width: info.width, height: info.height };

  const edgeMargins: EdgeMargins = {
    top: hasContent ? minY : 0,
    bottom: hasContent ? Math.max(0, info.height - 1 - maxY) : 0,
    left: hasContent ? minX : 0,
    right: hasContent ? Math.max(0, info.width - 1 - maxX) : 0,
  };

  return {
    format: metadata.format ?? "unknown",
    width,
    height,
    hasAlpha,
    hasTransparentPixels: hasAlpha && minAlpha < 255,
    transparentPixelRatio: totalPixels > 0 ? transparentCount / totalPixels : 0,
    boundingBox,
    edgeMargins,
    colorSpace: metadata.space ?? "srgb",
    densityDpi: metadata.density ?? 72,
    byteLength: bytes.byteLength,
    sha256: sha256(bytes),
  };
}
