import { encodeSelfTest } from "@etsy/image-pipeline";

export type ComponentStatus = "ok" | "degraded" | "down";

export interface ComponentHealth {
  readonly status: ComponentStatus;
  readonly detail?: string;
  readonly latencyMs?: number;
}

export interface HealthReport {
  readonly status: ComponentStatus;
  readonly service: "image-worker";
  readonly version: string;
  readonly checkedAt: string;
  readonly components: Readonly<Record<string, ComponentHealth>>;
}

/** Minimal contract the health check needs from a Redis client. */
export interface Pingable {
  ping(): Promise<string>;
}

async function timed(
  fn: () => Promise<void>,
): Promise<ComponentHealth> {
  const started = Date.now();
  try {
    await fn();
    return { status: "ok", latencyMs: Date.now() - started };
  } catch (cause) {
    return {
      status: "down",
      // Provider/connection errors can carry credentials in a URL; keep only
      // the message class, never the full error object.
      detail: (cause as Error).name,
      latencyMs: Date.now() - started,
    };
  }
}

/** Proves libvips can actually encode, not just that the module imported. */
export async function checkSharp(): Promise<ComponentHealth> {
  return timed(encodeSelfTest);
}

export async function checkRedis(client: Pingable): Promise<ComponentHealth> {
  return timed(async () => {
    const reply = await client.ping();
    if (reply !== "PONG") {
      throw new Error(`Unexpected PING reply: ${reply}`);
    }
  });
}

/** The report is "down" if any component is down, "degraded" if any is degraded. */
export function aggregate(
  components: Record<string, ComponentHealth>,
  version: string,
  now: Date,
): HealthReport {
  const statuses = Object.values(components).map((c) => c.status);
  const status: ComponentStatus = statuses.includes("down")
    ? "down"
    : statuses.includes("degraded")
      ? "degraded"
      : "ok";

  return {
    status,
    service: "image-worker",
    version,
    checkedAt: now.toISOString(),
    components,
  };
}
