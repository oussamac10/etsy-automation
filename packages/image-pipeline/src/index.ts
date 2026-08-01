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

export { encodeSelfTest, libvipsVersion } from "./selftest.js";

export { inspectImage, sha256 } from "./inspect.js";
export type { ImageFacts } from "./inspect.js";
