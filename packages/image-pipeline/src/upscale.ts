import sharp from "sharp";
import { DEFAULT_DECODE_LIMITS, type DecodeLimits } from "./limits.js";
import { DEFAULT_PRINT_PROFILE, type PrintProfile } from "./profiles.js";

export interface UpscaleOptions {
  readonly profile?: PrintProfile;
  readonly limits?: DecodeLimits;
}

export interface UpscaleResult {
  readonly buffer: Uint8Array;
  readonly width: number;
  readonly height: number;
  readonly densityDpi: number;
  readonly format: "png";
  readonly colorSpace: "sRGB";
}

/**
 * Upscale image proportionally onto the print canvas (4500×5400 px by default)
 * using the Lanczos3 kernel, transparent background, and 300 DPI density metadata.
 */
export async function upscaleToPrint(
  bytes: Uint8Array,
  options: UpscaleOptions = {},
): Promise<UpscaleResult> {
  const profile = options.profile ?? DEFAULT_PRINT_PROFILE;
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    // Allow large target master canvas up to 60MP
    maxPixels: 60_000_000,
  };

  // Resize proportionally into target canvas
  const upscaledBuffer = await sharp(bytes, { limitInputPixels: limits.maxPixels })
    .resize({
      width: profile.canvasWidth,
      height: profile.canvasHeight,
      fit: "contain",
      position: "center",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
      kernel: sharp.kernel.lanczos3,
    })
    .toColorspace("srgb")
    .png({ compressionLevel: 8 })
    .withMetadata({ density: profile.densityDpi })
    .toBuffer();

  return {
    buffer: new Uint8Array(upscaledBuffer),
    width: profile.canvasWidth,
    height: profile.canvasHeight,
    densityDpi: profile.densityDpi,
    format: "png",
    colorSpace: "sRGB",
  };
}
