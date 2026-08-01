import sharp from "sharp";

/**
 * Deterministic, original fixtures. Per tests/CLAUDE.md we never commit or
 * generate third-party artwork — these are flat geometric samples.
 */

export function opaqueSquare(size = 64, colour = { r: 200, g: 60, b: 40 }) {
  return sharp({
    create: {
      width: size,
      height: size,
      channels: 3,
      background: colour,
    },
  })
    .png()
    .toBuffer();
}

/** A PNG with an alpha channel where every pixel is fully opaque. */
export function opaqueAlphaSquare(size = 64) {
  return sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: { r: 10, g: 120, b: 90, alpha: 1 },
    },
  })
    .png()
    .toBuffer();
}

/** A PNG that is genuinely transparent. */
export function transparentSquare(size = 64) {
  return sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .png()
    .toBuffer();
}

export function jpegSquare(size = 64) {
  return sharp({
    create: {
      width: size,
      height: size,
      channels: 3,
      background: { r: 30, g: 30, b: 30 },
    },
  })
    .jpeg()
    .toBuffer();
}
