import Fastify, { type FastifyInstance } from "fastify";
import { randomUUID } from "node:crypto";
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

/**
 * Build the Fastify instance. Kept free of process/network setup so tests can
 * drive it through `app.inject()`.
 */
export function buildApp({ config, redis }: AppDependencies): FastifyInstance {
  const app = Fastify({
    logger: {
      level: pinoLevel(config.LOG_LEVEL),
      // Correlation IDs travel across api -> worker -> image-worker.
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

  return app;
}
