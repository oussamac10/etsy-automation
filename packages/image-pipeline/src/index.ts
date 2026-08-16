export {
  ALLOWED_INPUT_FORMATS,
  DEFAULT_DECODE_LIMITS,
  ImageRejected,
  assertAllowedFormat,
  assertWithinByteLimit,
  assertWithinPixelLimits,
} from "./limits.js";
export type {
  AllowedInputFormat,
  DecodeLimits,
  ImageRejectionCode,
} from "./limits.js";

export { createSolidPng, encodeSelfTest, libvipsVersion } from "./selftest.js";

export { DEFAULT_PRINT_PROFILE, PRINT_PROFILES } from "./profiles.js";
export type { PrintProfile, PrintProfileName } from "./profiles.js";

export { inspectImage, sha256 } from "./inspect.js";
export type { BoundingBox, EdgeMargins, ImageFacts } from "./inspect.js";

export { trimAndPad } from "./trim.js";
export type { TrimOptions, TrimResult } from "./trim.js";

export { upscaleToPrint } from "./upscale.js";
export type { UpscaleOptions, UpscaleResult } from "./upscale.js";

export {
  ALLOWED_FONTS,
  compositeTypography,
  generateTypographySvg,
  parseTypographyLayout,
} from "./typography.js";
export type {
  TypographyLayout,
  TypographyOptions,
  TypographyResult,
} from "./typography.js";

export { compositeCustomMockup, generateMockup, generateMugWrapCanvas, normalizeProductType } from "./mockup.js";
export type {
  CustomMockupPlacement,
  CustomMockupResult,
  MockupOptions,
  MockupProductType,
  MockupResult,
  MugWrapOptions,
  MugWrapResult,
} from "./mockup.js";

export { runQaReport } from "./qa.js";
export type { QaOptions, QaReport } from "./qa.js";

export {
  detectEdgeBackground,
  ensureTransparentBackground,
  removeEdgeConnectedBackground,
} from "./background.js";
export type {
  BackgroundDetectionResult,
  BackgroundRemovalOptions,
  BackgroundRemovalResult,
  RgbColor,
} from "./background.js";
