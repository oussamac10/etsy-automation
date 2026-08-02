import Redis from "ioredis";
import { buildApp } from "./app.js";
import { ConfigError, loadConfig } from "./config.js";

async function main(): Promise<void> {
  const config = loadConfig();

  const redis = new Redis(config.REDIS_URL, {
    lazyConnect: true,
    maxRetriesPerRequest: 2,
    // A failing dependency must show up in /health, not crash the process.
    enableOfflineQueue: false,
  });
  redis.on("error", (error: Error) => {
    process.stderr.write(`redis error: ${error.name}\n`);
  });
  void redis.connect().catch(() => undefined);

  const app = buildApp({ config, redis });

  const shutdown = async (signal: string): Promise<void> => {
    app.log.info({ signal }, "shutting down");
    await app.close();
    redis.disconnect();
    process.exit(0);
  };
  process.on("SIGTERM", () => void shutdown("SIGTERM"));
  process.on("SIGINT", () => void shutdown("SIGINT"));

  await app.listen({
    host: config.IMAGE_WORKER_HOST,
    port: config.IMAGE_WORKER_PORT,
  });
}

main().catch((error: unknown) => {
  if (error instanceof ConfigError) {
    process.stderr.write(`${error.message}\n`);
    process.exit(78); // EX_CONFIG
  }
  process.stderr.write(`image-worker failed to start: ${String(error)}\n`);
  process.exit(1);
});
