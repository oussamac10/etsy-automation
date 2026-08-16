import sharp from "sharp";
import {
  DEFAULT_DECODE_LIMITS,
  type DecodeLimits,
} from "./limits.js";

export interface RgbColor {
  readonly r: number;
  readonly g: number;
  readonly b: number;
}

export interface BackgroundDetectionResult {
  readonly detected: boolean;
  readonly isAlreadyTransparent: boolean;
  readonly isOpaqueNearWhite: boolean;
  readonly backgroundColor: RgbColor;
  readonly confidence: number;
  readonly edgeConnectedRatio: number;
  readonly cornersNearWhiteCount: number;
}

export interface BackgroundRemovalOptions {
  readonly tolerance?: number | undefined;
  readonly minBrightness?: number | undefined;
  readonly maxBorderVariance?: number | undefined;
  readonly featherRadius?: number | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface BackgroundRemovalResult {
  readonly buffer: Uint8Array;
  readonly width: number;
  readonly height: number;
  readonly modified: boolean;
  readonly detection: BackgroundDetectionResult;
  readonly removedPixelCount: number;
}

const DEFAULT_TOLERANCE = 30;
const DEFAULT_MIN_BRIGHTNESS = 230;
const DEFAULT_MAX_BORDER_VARIANCE = 30;

function colorDistanceSq(
  r1: number,
  g1: number,
  b1: number,
  r2: number,
  g2: number,
  b2: number,
): number {
  const dr = r1 - r2;
  const dg = g1 - g2;
  const db = b1 - b2;
  return dr * dr + dg * dg + db * db;
}

/**
 * Inspect corners and perimeter borders to detect if an image has a solid/near-white
 * edge-connected canvas background.
 */
export async function detectEdgeBackground(
  bytes: Uint8Array,
  options: BackgroundRemovalOptions = {},
): Promise<BackgroundDetectionResult> {
  const limits = options.limits ?? DEFAULT_DECODE_LIMITS;
  const minBrightness = options.minBrightness ?? DEFAULT_MIN_BRIGHTNESS;
  const maxVariance = options.maxBorderVariance ?? DEFAULT_MAX_BORDER_VARIANCE;

  const { data, info } = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = info.width;
  const height = info.height;

  // 1. Check corners
  const cornerCoords = [
    [0, 0],
    [width - 1, 0],
    [0, height - 1],
    [width - 1, height - 1],
  ];

  let transparentCornerCount = 0;
  let cornersNearWhiteCount = 0;
  let cornerRSum = 0;
  let cornerGSum = 0;
  let cornerBSum = 0;

  for (const [cx, cy] of cornerCoords) {
    const offset = (cy! * width + cx!) * 4;
    const r = data[offset] ?? 0;
    const g = data[offset + 1] ?? 0;
    const b = data[offset + 2] ?? 0;
    const a = data[offset + 3] ?? 255;

    if (a < 30) {
      transparentCornerCount++;
    } else if (r >= minBrightness && g >= minBrightness && b >= minBrightness) {
      cornersNearWhiteCount++;
      cornerRSum += r;
      cornerGSum += g;
      cornerBSum += b;
    }
  }

  // If already genuinely transparent at corners
  if (transparentCornerCount >= 3) {
    return {
      detected: false,
      isAlreadyTransparent: true,
      isOpaqueNearWhite: false,
      backgroundColor: { r: 255, g: 255, b: 255 },
      confidence: 1.0,
      edgeConnectedRatio: 0,
      cornersNearWhiteCount: 0,
    };
  }

  // 2. Sample perimeter pixels
  const borderPixels: RgbColor[] = [];
  let borderTransparentCount = 0;

  for (let x = 0; x < width; x += Math.max(1, Math.floor(width / 64))) {
    // top & bottom
    for (const y of [0, height - 1]) {
      const offset = (y * width + x) * 4;
      const a = data[offset + 3] ?? 255;
      if (a < 30) {
        borderTransparentCount++;
      } else {
        borderPixels.push({
          r: data[offset] ?? 0,
          g: data[offset + 1] ?? 0,
          b: data[offset + 2] ?? 0,
        });
      }
    }
  }

  for (let y = 0; y < height; y += Math.max(1, Math.floor(height / 64))) {
    // left & right
    for (const x of [0, width - 1]) {
      const offset = (y * width + x) * 4;
      const a = data[offset + 3] ?? 255;
      if (a < 30) {
        borderTransparentCount++;
      } else {
        borderPixels.push({
          r: data[offset] ?? 0,
          g: data[offset + 1] ?? 0,
          b: data[offset + 2] ?? 0,
        });
      }
    }
  }

  if (borderPixels.length === 0) {
    return {
      detected: false,
      isAlreadyTransparent: true,
      isOpaqueNearWhite: false,
      backgroundColor: { r: 255, g: 255, b: 255 },
      confidence: 1.0,
      edgeConnectedRatio: 0,
      cornersNearWhiteCount,
    };
  }

  let rSum = 0;
  let gSum = 0;
  let bSum = 0;
  let nearWhiteBorderCount = 0;

  for (const p of borderPixels) {
    rSum += p.r;
    gSum += p.g;
    bSum += p.b;
    if (p.r >= minBrightness && p.g >= minBrightness && p.b >= minBrightness) {
      nearWhiteBorderCount++;
    }
  }

  const meanR = rSum / borderPixels.length;
  const meanG = gSum / borderPixels.length;
  const meanB = bSum / borderPixels.length;

  let varSum = 0;
  for (const p of borderPixels) {
    const dr = p.r - meanR;
    const dg = p.g - meanG;
    const db = p.b - meanB;
    varSum += Math.sqrt((dr * dr + dg * dg + db * db) / 3);
  }
  const avgVariance = varSum / borderPixels.length;

  const isNearWhite = meanR >= minBrightness && meanG >= minBrightness && meanB >= minBrightness;
  const isUniformBorder = avgVariance <= maxVariance;
  const isOpaqueNearWhite = isNearWhite && isUniformBorder && cornersNearWhiteCount >= 3;

  const bgR = cornersNearWhiteCount > 0 ? Math.round(cornerRSum / cornersNearWhiteCount) : Math.round(meanR);
  const bgG = cornersNearWhiteCount > 0 ? Math.round(cornerGSum / cornersNearWhiteCount) : Math.round(meanG);
  const bgB = cornersNearWhiteCount > 0 ? Math.round(cornerBSum / cornersNearWhiteCount) : Math.round(meanB);

  return {
    detected: isOpaqueNearWhite,
    isAlreadyTransparent: false,
    isOpaqueNearWhite,
    backgroundColor: { r: bgR, g: bgG, b: bgB },
    confidence: isOpaqueNearWhite ? 0.95 : 0.2,
    edgeConnectedRatio: nearWhiteBorderCount / borderPixels.length,
    cornersNearWhiteCount,
  };
}

/**
 * Remove edge-connected background using a strict border-connected flood-fill (BFS).
 *
 * Guaranteed to preserve interior/isolated white artwork details (book pages, steam,
 * mugs, stars, highlights) while setting outer canvas background to alpha=0.
 */
export async function removeEdgeConnectedBackground(
  bytes: Uint8Array,
  options: BackgroundRemovalOptions = {},
): Promise<BackgroundRemovalResult> {
  const limits = options.limits ?? DEFAULT_DECODE_LIMITS;
  const tolerance = options.tolerance ?? DEFAULT_TOLERANCE;
  const minBrightness = options.minBrightness ?? DEFAULT_MIN_BRIGHTNESS;

  const detection = await detectEdgeBackground(bytes, options);

  if (detection.isAlreadyTransparent && !detection.detected) {
    const rawPng = await sharp(bytes, { limitInputPixels: limits.maxPixels })
      .png({ compressionLevel: 9 })
      .toBuffer();
    return {
      buffer: new Uint8Array(rawPng),
      width: 0,
      height: 0,
      modified: false,
      detection,
      removedPixelCount: 0,
    };
  }

  const { data, info } = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = info.width;
  const height = info.height;
  const totalPixels = width * height;
  const toleranceSq = tolerance * tolerance;

  const bgR = detection.backgroundColor.r;
  const bgG = detection.backgroundColor.g;
  const bgB = detection.backgroundColor.b;

  // Bitset / Uint8Array to track visited background pixels
  const isBg = new Uint8Array(totalPixels);
  const queueX = new Int32Array(totalPixels);
  const queueY = new Int32Array(totalPixels);
  let head = 0;
  let tail = 0;

  function isBackgroundCandidate(x: number, y: number): boolean {
    const idx = (y * width + x) * 4;
    const a = data[idx + 3] ?? 255;
    if (a < 30) return true;

    const r = data[idx] ?? 0;
    const g = data[idx + 1] ?? 0;
    const b = data[idx + 2] ?? 0;

    // Check color distance to detected background
    const distSq = colorDistanceSq(r, g, b, bgR, bgG, bgB);
    if (distSq <= toleranceSq) {
      return true;
    }

    // Also accept any near-white if it connects to the background
    if (r >= minBrightness && g >= minBrightness && b >= minBrightness) {
      const channelMaxDiff = Math.max(Math.abs(r - bgR), Math.abs(g - bgG), Math.abs(b - bgB));
      if (channelMaxDiff <= tolerance + 10) {
        return true;
      }
    }

    return false;
  }

  // 1. Seed BFS strictly from outer border perimeter
  for (let x = 0; x < width; x++) {
    for (const y of [0, height - 1]) {
      const idx = y * width + x;
      if (!isBg[idx] && isBackgroundCandidate(x, y)) {
        isBg[idx] = 1;
        queueX[tail] = x;
        queueY[tail] = y;
        tail++;
      }
    }
  }

  for (let y = 0; y < height; y++) {
    for (const x of [0, width - 1]) {
      const idx = y * width + x;
      if (!isBg[idx] && isBackgroundCandidate(x, y)) {
        isBg[idx] = 1;
        queueX[tail] = x;
        queueY[tail] = y;
        tail++;
      }
    }
  }

  // 2. Flood Fill BFS
  while (head < tail) {
    const cx = queueX[head]!;
    const cy = queueY[head]!;
    head++;

    const neighbors = [
      [cx - 1, cy],
      [cx + 1, cy],
      [cx, cy - 1],
      [cx, cy + 1],
    ];

    for (const [nx, ny] of neighbors) {
      if (nx! >= 0 && nx! < width && ny! >= 0 && ny! < height) {
        const nIdx = ny! * width + nx!;
        if (!isBg[nIdx] && isBackgroundCandidate(nx!, ny!)) {
          isBg[nIdx] = 1;
          queueX[tail] = nx!;
          queueY[tail] = ny!;
          tail++;
        }
      }
    }
  }

  // 3. Clear Alpha for background pixels & apply boundary anti-halo de-fringing
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const pIdx = y * width + x;
      const offset = pIdx * 4;

      if (isBg[pIdx]) {
        data[offset + 3] = 0; // Fully transparent
      } else {
        // Check if this is an edge boundary pixel adjacent to background
        let adjacentBgCount = 0;
        if (x > 0 && isBg[pIdx - 1]) adjacentBgCount++;
        if (x < width - 1 && isBg[pIdx + 1]) adjacentBgCount++;
        if (y > 0 && isBg[pIdx - width]) adjacentBgCount++;
        if (y < height - 1 && isBg[pIdx + width]) adjacentBgCount++;

        if (adjacentBgCount > 0) {
          const r = data[offset] ?? 0;
          const g = data[offset + 1] ?? 0;
          const b = data[offset + 2] ?? 0;
          const a = data[offset + 3] ?? 255;

          // If adjacent pixel is very light (mixed with white background), de-fringe
          if (r >= 210 && g >= 210 && b >= 210) {
            // Soften alpha slightly at outer boundary for smooth antialiasing without harsh white edges
            const alphaFactor = adjacentBgCount >= 2 ? 0.6 : 0.85;
            data[offset + 3] = Math.round(a * alphaFactor);
          }
        }
      }
    }
  }

  const resultPng = await sharp(data, {
    raw: { width, height, channels: 4 },
  })
    .png({ compressionLevel: 9 })
    .toBuffer();

  return {
    buffer: new Uint8Array(resultPng),
    width,
    height,
    modified: tail > 0,
    detection,
    removedPixelCount: tail,
  };
}

/**
 * Ensure image has genuine alpha transparency. If an edge-connected near-white background
 * is detected, removes it cleanly while preserving interior white details.
 */
export async function ensureTransparentBackground(
  bytes: Uint8Array,
  options: BackgroundRemovalOptions = {},
): Promise<BackgroundRemovalResult> {
  const detection = await detectEdgeBackground(bytes, options);

  if (detection.detected) {
    return removeEdgeConnectedBackground(bytes, options);
  }

  // Already transparent or non-near-white background
  const limits = options.limits ?? DEFAULT_DECODE_LIMITS;
  const rawPng = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .ensureAlpha()
    .png({ compressionLevel: 9 })
    .toBuffer();

  return {
    buffer: new Uint8Array(rawPng),
    width: 0,
    height: 0,
    modified: false,
    detection,
    removedPixelCount: 0,
  };
}
