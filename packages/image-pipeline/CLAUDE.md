# CLAUDE.md — Image Pipeline

These rules extend the root instructions for `packages/image-pipeline`.

## Responsibilities

- Validate source files
- Normalize color space and orientation
- Detect alpha channel and opaque borders
- Remove background through a provider adapter when needed
- Trim with safe padding without cropping content
- Add typography from controlled SVG templates
- Upscale through a provider adapter when selected
- Render deterministic product mockups from licensed templates
- Produce final PNG and QA report

## Output contract

The final production asset must have:

- PNG format
- expected dimensions recorded
- transparent background verified when required
- sRGB color profile
- uncropped foreground with configured safe margin
- no unexpected opaque corner pixels
- SHA-256 recorded
- source and operation provenance

Do not write or claim a DPI value as proof of print quality. Pixel dimensions and visual QA matter.

## Safety

- Enforce input byte, pixel, width, height, and frame limits before decoding.
- Disable network access from SVG rendering.
- Reject scripts, external resources, and unsupported formats.
- Use generated safe filenames; never trust uploaded names as paths.
- Archive entries must be generated from a whitelist and a manifest.

## Typography

- AI-generated text is never the final phrase.
- Use licensed fonts stored with documented licence metadata.
- Render exact user-approved text through SVG/Sharp.
- Test line wrapping, safe area, contrast, and spelling.
- Preserve a text-free artwork master.

## QA

Automated QA flags issues; it does not replace artwork approval. Tests use fixture images for alpha, crop, edge halo, oversize, corrupt, and malicious SVG cases.
