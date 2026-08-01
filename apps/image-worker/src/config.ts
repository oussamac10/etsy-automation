import { z } from "zod";

/**
 * Environment validation at startup (root CLAUDE.md: "Configuration comes from
 * environment variables validated at startup"). An invalid environment must
 * stop the process, not surface as an undefined at request time.
 */
const schema = z.object({
  APP_ENV: z.enum(["local", "staging", "production"]).default("local"),
  // The shared .env uses upper-case levels (INFO); pino wants lower case.
  LOG_LEVEL: z.preprocess(
    (value) => (typeof value === "string" ? value.toLowerCase() : value),
    z.enum(["debug", "info", "warn", "warning", "error"]).default("info"),
  ),
  IMAGE_WORKER_HOST: z.string().min(1).default("0.0.0.0"),
  IMAGE_WORKER_PORT: z.coerce.number().int().min(1).max(65535).default(8100),
  REDIS_URL: z.string().min(1).default("redis://localhost:6379/0"),
  IMAGE_MAX_INPUT_BYTES: z.coerce
    .number()
    .int()
    .positive()
    .default(40 * 1024 * 1024),
  IMAGE_MAX_PIXELS: z.coerce.number().int().positive().default(50_000_000),
});

export type Config = z.infer<typeof schema>;

export class ConfigError extends Error {
  constructor(issues: string[]) {
    super(`Invalid environment:\n  - ${issues.join("\n  - ")}`);
    this.name = "ConfigError";
  }
}

/** Parse and validate an environment map. Pure, so tests can pass a fixture. */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  // Empty strings in a .env file must fall back to the default, not fail.
  const cleaned = Object.fromEntries(
    Object.entries(env).filter(([, value]) => value !== undefined && value !== ""),
  );

  const result = schema.safeParse(cleaned);
  if (!result.success) {
    throw new ConfigError(
      result.error.issues.map(
        (issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`,
      ),
    );
  }
  return result.data;
}

/** pino has no "warning" level; map the Python-style name onto "warn". */
export function pinoLevel(level: Config["LOG_LEVEL"]): string {
  return level === "warning" ? "warn" : level;
}
