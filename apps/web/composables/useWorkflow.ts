import { z } from "zod";
import { RUN_STATUSES } from "@etsy/domain";

/**
 * The pipeline description comes from the API rather than a local constant, so
 * the UI can never advertise a stage the backend does not implement.
 */

export const workflowSchema = z.object({
  states: z.array(z.string()).min(1),
  failure_states: z.array(z.string()),
  gates: z.array(
    z.object({
      gate: z.string(),
      decided_from: z.string(),
      advances_to: z.string(),
    }),
  ),
  risk_levels: z.array(z.string()),
  publishes_automatically: z.boolean(),
});

export type WorkflowDescription = z.infer<typeof workflowSchema>;

export function parseWorkflow(payload: unknown): WorkflowDescription {
  const result = workflowSchema.safeParse(payload);
  if (!result.success) {
    throw new Error("Unexpected /api/v1/workflow payload");
  }
  const workflow = result.data;

  // A build that could publish on its own would violate the product rule, so
  // the client refuses the payload rather than rendering it.
  if (workflow.publishes_automatically) {
    throw new Error(
      "API reported automatic publishing, which this product does not support.",
    );
  }
  return workflow;
}

/** The pipeline the client knows about, used until the API responds. */
export const FALLBACK_STATES: readonly string[] = RUN_STATUSES;

export async function fetchWorkflow(
  base: string,
  fetcher: typeof $fetch = $fetch,
): Promise<WorkflowDescription> {
  const payload = await fetcher<unknown>(
    `${base.replace(/\/$/, "")}/api/v1/workflow`,
  );
  return parseWorkflow(payload);
}
