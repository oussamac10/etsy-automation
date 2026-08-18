import Fastify, { type FastifyInstance } from "fastify";
import { randomUUID } from "node:crypto";
import {
  compositeCustomMockup,
  compositeTypography,
  DEFAULT_PRINT_PROFILE,
  detectEdgeBackground,
  ensureTransparentBackground,
  generateMockup,
  generateMugWrapCanvas,
  ImageRejected,
  inspectImage,
  parseTypographyLayout,
  runQaReport,
  trimAndPad,
  upscaleToPrint,
  type BackgroundRemovalOptions,
  type CustomMockupPlacement,
  type MockupProductType,
  type TypographyLayout,
} from "@etsy/image-pipeline";
import type { Config } from "./config.js";
import { pinoLevel } from "./config.js";
import {
  aggregate,
  checkRedis,
  checkSharp,
  type Pingable,
} from "./health.js";

export const SERVICE_VERSION = "0.1.0";

export interface AppDependencies {
  readonly config: Config;
  /** Injected so tests never open a socket. */
  readonly redis: Pingable;
}

function decodeBase64(dataUrlOrBase64: string): Uint8Array {
  const base64Data = dataUrlOrBase64.includes(",")
    ? dataUrlOrBase64.split(",")[1]!
    : dataUrlOrBase64;
  return new Uint8Array(Buffer.from(base64Data, "base64"));
}

function toBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64");
}

/**
 * Build the Fastify instance. Kept free of process/network setup so tests can
 * drive it through `app.inject()`.
 */
export function buildApp({ config, redis }: AppDependencies): FastifyInstance {
  const app = Fastify({
    bodyLimit: config.IMAGE_MAX_INPUT_BYTES ?? 150 * 1024 * 1024,
    logger: {
      level: pinoLevel(config.LOG_LEVEL),
      redact: {
        paths: ["req.headers.authorization", "req.headers.cookie"],
        censor: "[redacted]",
      },
    },
    genReqId: (req) =>
      (req.headers["x-correlation-id"] as string | undefined) ?? randomUUID(),
    disableRequestLogging: config.APP_ENV === "local",
  });

  app.addHook("onSend", async (request, reply) => {
    void reply.header("x-correlation-id", request.id);
  });

  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof ImageRejected) {
      return reply.status(422).send({
        error: "IMAGE_REJECTED",
        code: error.code,
        message: error.message,
      });
    }
    const err = error as Error;
    app.log.error(err);
    return reply.status(500).send({
      error: "INTERNAL_ERROR",
      message: err.message || "An unexpected error occurred during image processing.",
    });
  });

  /** Liveness: the process is up. Never touches a dependency. */
  app.get("/health/live", async () => ({
    status: "ok",
    service: "image-worker",
    version: SERVICE_VERSION,
  }));

  /** Readiness: libvips works and Redis answers. Used by Docker Compose. */
  app.get("/health", async (_request, reply) => {
    const [sharpHealth, redisHealth] = await Promise.all([
      checkSharp(),
      checkRedis(redis),
    ]);

    const report = aggregate(
      { sharp: sharpHealth, redis: redisHealth },
      SERVICE_VERSION,
      new Date(),
    );

    return reply.status(report.status === "ok" ? 200 : 503).send(report);
  });

  /** 1. Analyze */
  app.post<{ Body: { image_base64: string } }>("/pipeline/analyze", async (request, reply) => {
    if (!request.body?.image_base64) {
      return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const facts = await inspectImage(bytes);
    return reply.send({ facts });
  });

  /** 2. Safe Trim & Pad */
  app.post<{ Body: { image_base64: string; margin_percent?: number } }>(
    "/pipeline/trim-and-pad",
    async (request, reply) => {
      if (!request.body?.image_base64) {
        return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
      }
      const bytes = decodeBase64(request.body.image_base64);
      const result = await trimAndPad(bytes, { marginPercent: request.body.margin_percent });
      return reply.send({
        image_base64: toBase64(result.buffer),
        original_width: result.originalWidth,
        original_height: result.originalHeight,
        trimmed_width: result.trimmedWidth,
        trimmed_height: result.trimmedHeight,
        padded_width: result.paddedWidth,
        padded_height: result.paddedHeight,
      });
    },
  );

  /** 3. Upscale to Print Profile */
  app.post<{ Body: { image_base64: string } }>("/pipeline/upscale", async (request, reply) => {
    if (!request.body?.image_base64) {
      return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const result = await upscaleToPrint(bytes);
    return reply.send({
      image_base64: toBase64(result.buffer),
      width: result.width,
      height: result.height,
      density_dpi: result.densityDpi,
      format: result.format,
      color_space: result.colorSpace,
    });
  });

  /** 4. Slogan Typography Composite */
  app.post<{
    Body: {
      image_base64: string;
      slogan: string;
      layout?: TypographyLayout;
      font_family?: string;
      fill?: string;
    };
  }>("/pipeline/composite", async (request, reply) => {
    if (!request.body?.image_base64 || !request.body?.slogan) {
      return reply
        .status(400)
        .send({ error: "MISSING_REQUIRED_FIELDS", message: "image_base64 and slogan are required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const result = await compositeTypography(bytes, {
      slogan: request.body.slogan,
      layout: request.body.layout,
      fontFamily: request.body.font_family,
      fill: request.body.fill,
    });
    return reply.send({
      image_base64: toBase64(result.buffer),
      slogan_rendered: result.sloganRendered,
      layout: result.layout,
      font_family: result.fontFamily,
      fill: result.fill,
    });
  });

  /** 5. Mockup Generation */
  app.post<{
    Body: {
      image_base64: string;
      product_type: MockupProductType;
      garment_color?: "white" | "black" | "heather_gray" | "natural";
      output_size?: number;
    };
  }>("/pipeline/mockup", async (request, reply) => {
    if (!request.body?.image_base64 || !request.body?.product_type) {
      return reply
        .status(400)
        .send({ error: "MISSING_REQUIRED_FIELDS", message: "image_base64 and product_type are required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const result = await generateMockup(bytes, {
      productType: request.body.product_type,
      garmentColor: request.body.garment_color,
      outputSize: request.body.output_size,
    });
    return reply.send({
      image_base64: toBase64(result.buffer),
      product_type: result.productType,
      width: result.width,
      height: result.height,
    });
  });

  /** Mug Wrap Canvas Generator for Provider Wrap Templates */
  app.post<{
    Body: {
      image_base64: string;
      layout_mode?: "front_focus" | "dual_sided" | "full_wrap";
      scale?: number;
      safe_margin_px?: number;
    };
  }>("/pipeline/mug-wrap", async (request, reply) => {
    if (!request.body?.image_base64) {
      return reply
        .status(400)
        .send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const result = await generateMugWrapCanvas(bytes, {
      layoutMode: request.body.layout_mode,
      scale: request.body.scale,
      safeMarginPx: request.body.safe_margin_px,
    });
    return reply.send({
      wrap_image_base64: toBase64(result.buffer),
      width: result.width,
      height: result.height,
      placement_box: result.placementBox,
    });
  });

  /** 6. QA Validation */
  app.post<{ Body: { image_base64: string; exact_slogan?: string } }>(
    "/pipeline/qa",
    async (request, reply) => {
      if (!request.body?.image_base64) {
        return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
      }
      const bytes = decodeBase64(request.body.image_base64);
      const report = await runQaReport(bytes, { exactSlogan: request.body.exact_slogan });
      return reply.send({ qa_report: report });
    },
  );

  /** Custom Mockup Compositing */
  app.post<{
    Body: {
      artwork_base64: string;
      template_base64: string;
      placement?: CustomMockupPlacement;
      format?: "jpeg" | "png";
      quality?: number;
    };
  }>("/pipeline/custom-mockup", async (request, reply) => {
    if (!request.body?.artwork_base64) {
      return reply.status(400).send({ error: "MISSING_ARTWORK", message: "artwork_base64 is required" });
    }
    if (!request.body?.template_base64) {
      return reply.status(400).send({ error: "MISSING_TEMPLATE", message: "template_base64 is required" });
    }

    const artworkBytes = decodeBase64(request.body.artwork_base64);
    const templateBytes = decodeBase64(request.body.template_base64);

    const result = await compositeCustomMockup(artworkBytes, templateBytes, {
      placement: request.body.placement,
      format: request.body.format ?? "jpeg",
      quality: request.body.quality ?? 90,
    });

    return reply.send({
      mockup_base64: toBase64(result.buffer),
      width: result.width,
      height: result.height,
      format: result.format,
    });
  });

  /** 7. Background Transparency Cleanup */
  app.post<{
    Body: {
      image_base64: string;
      options?: BackgroundRemovalOptions;
    };
  }>("/pipeline/ensure-transparency", async (request, reply) => {
    if (!request.body?.image_base64) {
      return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
    }
    const bytes = decodeBase64(request.body.image_base64);
    const result = await ensureTransparentBackground(bytes, request.body.options);
    return reply.send({
      image_base64: toBase64(result.buffer),
      width: result.width,
      height: result.height,
      modified: result.modified,
      detection: result.detection,
      removed_pixel_count: result.removedPixelCount,
    });
  });

  /** 8. Full Orchestrated Master Processing */
  app.post<{
    Body: {
      image_base64: string;
      exact_slogan?: string | null;
      typography_instructions?: string | null;
      intended_products?: MockupProductType[];
    };
  }>("/pipeline/process-master", async (request, reply) => {
    if (!request.body?.image_base64) {
      return reply.status(400).send({ error: "MISSING_IMAGE", message: "image_base64 is required" });
    }

    let initialBytes = decodeBase64(request.body.image_base64);

    // Defense in depth: Clean edge-connected near-white background if detected
    const bgCheck = await detectEdgeBackground(initialBytes);
    if (bgCheck.detected) {
      const cleaned = await ensureTransparentBackground(initialBytes);
      initialBytes = cleaned.buffer;
    }

    // Step 1: Trim & Pad
    const trimmed = await trimAndPad(initialBytes, { marginPercent: DEFAULT_PRINT_PROFILE.defaultMarginPercent });

    // Step 2: Upscale to 4500x5400
    const upscaled = await upscaleToPrint(trimmed.buffer);

    // Step 3: Typography Composite (if exact slogan exists)
    let masterBuffer = upscaled.buffer;
    let typographyApplied = false;
    if (request.body.exact_slogan && request.body.exact_slogan.trim().length > 0) {
      const layout = parseTypographyLayout(request.body.typography_instructions);
      const composited = await compositeTypography(masterBuffer, {
        slogan: request.body.exact_slogan.trim(),
        layout,
      });
      masterBuffer = composited.buffer;
      typographyApplied = true;
    }

    // Step 4: Run QA Report
    const qaReport = await runQaReport(masterBuffer, {
      exactSlogan: request.body.exact_slogan ?? undefined,
    });

    return reply.send({
      master_png_base64: toBase64(masterBuffer),
      typography_applied: typographyApplied,
      qa_report: qaReport,
      mockups: {},
    });
  });

  return app;
}

