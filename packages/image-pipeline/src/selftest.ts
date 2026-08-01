import sharp from "sharp";

/**
 * Prove the native libvips binding can actually encode a PNG.
 *
 * Importing Sharp succeeds even when its platform binary is missing or
 * mismatched, so the health check has to do real work.
 */
export async function encodeSelfTest(): Promise<void> {
  const png = await sharp({
    create: {
      width: 8,
      height: 8,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .png()
    .toBuffer();

  if (png.byteLength === 0) {
    throw new Error("Sharp produced an empty PNG.");
  }
}

/** The libvips version behind Sharp, for the health payload. */
export function libvipsVersion(): string {
  return sharp.versions.vips;
}
