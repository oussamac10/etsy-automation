/**
 * Decode guards. Every limit is checked *before* the bytes reach Sharp so a
 * decompression bomb cannot allocate memory first.
 */

export interface DecodeLimits {
  readonly maxBytes: number;
  readonly maxPixels: number;
  readonly maxWidth: number;
  readonly maxHeight: number;
}

export const DEFAULT_DECODE_LIMITS: DecodeLimits = Object.freeze({
  maxBytes: 40 * 1024 * 1024,
  maxPixels: 50_000_000,
  maxWidth: 20_000,
  maxHeight: 20_000,
});

/** Formats we are willing to decode. SVG is excluded: it is rendered only through the hardened typography path. */
export const ALLOWED_INPUT_FORMATS = Object.freeze([
  "png",
  "jpeg",
  "webp",
  "tiff",
] as const);

export type AllowedInputFormat = (typeof ALLOWED_INPUT_FORMATS)[number];

export type ImageRejectionCode =
  | "TOO_LARGE"
  | "TOO_MANY_PIXELS"
  | "UNSUPPORTED_FORMAT"
  | "UNREADABLE";

export class ImageRejected extends Error {
  readonly code: ImageRejectionCode;

  constructor(message: string, code: ImageRejectionCode) {
    super(message);
    this.name = "ImageRejected";
    this.code = code;
  }
}

/** Reject oversized payloads by byte length before any decode is attempted. */
export function assertWithinByteLimit(
  bytes: number,
  limits: DecodeLimits = DEFAULT_DECODE_LIMITS,
): void {
  if (bytes > limits.maxBytes) {
    throw new ImageRejected(
      `Input is ${bytes} bytes; limit is ${limits.maxBytes}.`,
      "TOO_LARGE",
    );
  }
}

export function assertWithinPixelLimits(
  width: number,
  height: number,
  limits: DecodeLimits = DEFAULT_DECODE_LIMITS,
): void {
  if (width > limits.maxWidth || height > limits.maxHeight) {
    throw new ImageRejected(
      `Input is ${width}x${height}; limit is ${limits.maxWidth}x${limits.maxHeight}.`,
      "TOO_MANY_PIXELS",
    );
  }
  if (width * height > limits.maxPixels) {
    throw new ImageRejected(
      `Input has ${width * height} pixels; limit is ${limits.maxPixels}.`,
      "TOO_MANY_PIXELS",
    );
  }
}

export function assertAllowedFormat(format: string | undefined): void {
  if (
    format === undefined ||
    !(ALLOWED_INPUT_FORMATS as readonly string[]).includes(format)
  ) {
    throw new ImageRejected(
      `Format ${format ?? "unknown"} is not accepted.`,
      "UNSUPPORTED_FORMAT",
    );
  }
}
