import { z } from "zod";

/**
 * Typed access to the API health endpoint.
 *
 * Provider/API responses are untrusted input (root CLAUDE.md), so the payload
 * is validated with zod before any component reads it.
 */

const componentSchema = z.object({
  status: z.enum(["ok", "degraded", "down"]),
  detail: z.string().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
});

export const healthSchema = z.object({
  status: z.enum(["ok", "degraded", "down"]),
  service: z.string(),
  version: z.string(),
  app_env: z.string(),
  checked_at: z.string(),
  components: z.record(z.string(), componentSchema),
});

export type ApiHealth = z.infer<typeof healthSchema>;

export class ApiResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiResponseError";
  }
}

/** Parse an unknown payload into a health report, or throw. */
export function parseHealth(payload: unknown): ApiHealth {
  const result = healthSchema.safeParse(payload);
  if (!result.success) {
    throw new ApiResponseError(
      `Unexpected /api/health payload: ${result.error.issues
        .map((issue) => issue.path.join("."))
        .join(", ")}`,
    );
  }
  return result.data;
}

export function useApiBase(): string {
  return useRuntimeConfig().public.apiBase;
}

/** Fetch and validate the API health report. */
export async function fetchApiHealth(
  base: string,
  fetcher: typeof $fetch = $fetch,
): Promise<ApiHealth> {
  const payload = await fetcher<unknown>(`${base.replace(/\/$/, "")}/api/health`);
  return parseHealth(payload);
}
