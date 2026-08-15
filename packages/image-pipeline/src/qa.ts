import { inspectImage, type ImageFacts } from "./inspect.js";
import { DEFAULT_DECODE_LIMITS, type DecodeLimits } from "./limits.js";
import { DEFAULT_PRINT_PROFILE, type PrintProfile } from "./profiles.js";

export interface QaOptions {
  readonly profile?: PrintProfile | undefined;
  readonly exactSlogan?: string | null | undefined;
  readonly limits?: DecodeLimits | undefined;
}

export interface QaReport {
  readonly dimensions_valid: boolean;
  readonly width: number;
  readonly height: number;
  readonly target_width: number;
  readonly target_height: number;
  readonly density_dpi: number;
  readonly target_dpi: number;
  readonly has_alpha: boolean;
  readonly has_transparent_pixels: boolean;
  readonly transparent_background_valid: boolean;
  readonly safe_margins_valid: boolean;
  readonly cropped_edges_detected: boolean;
  readonly edge_margins: {
    readonly top: number;
    readonly bottom: number;
    readonly left: number;
    readonly right: number;
  };
  readonly color_space: string;
  readonly file_size_bytes: number;
  readonly checksum_sha256: string;
  readonly typography_applied: boolean;
  readonly exact_slogan_recorded: string | null;
  readonly warnings: string[];
  readonly qa_passed: boolean;
}

/**
 * Execute comprehensive quality assurance validation on a production master PNG.
 */
export async function runQaReport(
  bytes: Uint8Array,
  options: QaOptions = {},
): Promise<QaReport> {
  const profile = options.profile ?? DEFAULT_PRINT_PROFILE;
  const limits = options.limits ?? {
    ...DEFAULT_DECODE_LIMITS,
    maxPixels: 60_000_000,
  };

  const facts: ImageFacts = await inspectImage(bytes, limits);
  const warnings: string[] = [];

  const dimensionsValid = facts.width === profile.canvasWidth && facts.height === profile.canvasHeight;
  if (!dimensionsValid) {
    warnings.push(`Dimensions ${facts.width}x${facts.height} do not match target ${profile.canvasWidth}x${profile.canvasHeight}.`);
  }

  const dpiValid = facts.densityDpi >= profile.densityDpi;
  if (!dpiValid && facts.densityDpi < 300) {
    warnings.push(`Density ${facts.densityDpi} DPI is below target 300 DPI.`);
  }

  if (!facts.hasAlpha || !facts.hasTransparentPixels) {
    warnings.push("Image does not contain transparent pixels or alpha channel.");
  }

  // Check margins & cropped edges
  const minSafeMarginX = Math.round(profile.canvasWidth * 0.015);
  const minSafeMarginY = Math.round(profile.canvasHeight * 0.015);

  const croppedEdgesDetected =
    facts.edgeMargins.top === 0 ||
    facts.edgeMargins.bottom === 0 ||
    facts.edgeMargins.left === 0 ||
    facts.edgeMargins.right === 0;

  if (croppedEdgesDetected) {
    warnings.push("Artwork touches canvas edges directly; possible cropping or unpadded boundary.");
  }

  const safeMarginsValid =
    facts.edgeMargins.top >= minSafeMarginX &&
    facts.edgeMargins.bottom >= minSafeMarginY &&
    facts.edgeMargins.left >= minSafeMarginX &&
    facts.edgeMargins.right >= minSafeMarginX;

  const transparentBackgroundValid = facts.hasTransparentPixels && facts.transparentPixelRatio > 0.1;

  const typographyApplied = !!options.exactSlogan && options.exactSlogan.trim().length > 0;

  const criticalFailures = !dimensionsValid || !facts.hasAlpha || !facts.hasTransparentPixels;
  const qaPassed = !criticalFailures;

  return {
    dimensions_valid: dimensionsValid,
    width: facts.width,
    height: facts.height,
    target_width: profile.canvasWidth,
    target_height: profile.canvasHeight,
    density_dpi: facts.densityDpi,
    target_dpi: profile.densityDpi,
    has_alpha: facts.hasAlpha,
    has_transparent_pixels: facts.hasTransparentPixels,
    transparent_background_valid: transparentBackgroundValid,
    safe_margins_valid: safeMarginsValid,
    cropped_edges_detected: croppedEdgesDetected,
    edge_margins: facts.edgeMargins,
    color_space: facts.colorSpace,
    file_size_bytes: facts.byteLength,
    checksum_sha256: facts.sha256,
    typography_applied: typographyApplied,
    exact_slogan_recorded: options.exactSlogan ?? null,
    warnings,
    qa_passed: qaPassed,
  };
}
