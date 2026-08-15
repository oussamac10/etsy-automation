import { ref } from "vue";
import { HAPPY_PATH, IN_FLIGHT_STATUSES } from "@etsy/domain";

/**
 * Stopping and restarting a campaign, shared by the campaign list and the
 * campaign page so both offer the action under exactly the same conditions.
 */

/**
 * A queued or running job owns the campaign. Stopping only means something
 * while work is in flight: a campaign waiting at a review gate is already
 * paused, and one that finished has nothing left to interrupt. The list comes
 * from the shared domain mirror so it cannot drift from what the API enforces.
 */
export function isRunning(state: string): boolean {
  return (IN_FLIGHT_STATUSES as readonly string[]).includes(state);
}

/** Only a stopped campaign can be rerun, and it restarts from the brief. */
export function isStopped(state: string): boolean {
  return state === "CANCELLED";
}

/**
 * Deleting is refused while a worker still holds the campaign, so the owner
 * stops it first. The API enforces the same rule.
 */
export function canDelete(state: string): boolean {
  return !isRunning(state);
}

/** Stage names in the owner's words, not the state machine's. */
const STAGE_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  RESEARCH_QUEUED: "Research queued",
  RESEARCHING: "Researching",
  IDEA_REVIEW: "Waiting for you: idea",
  IDEA_APPROVED: "Idea approved",
  ART_QUEUED: "Artwork queued",
  ART_GENERATION: "Generating artwork",
  ART_REVIEW: "Waiting for you: artwork",
  ARTWORK_APPROVED: "Artwork approved",
  PRODUCTION: "Preparing files",
  IP_REVIEW: "IP review",
  LISTING_REVIEW: "Waiting for you: listing",
  READY_FOR_ETSY_DRAFT: "Ready for Etsy draft",
  ETSY_DRAFT_CREATED: "Etsy draft created",
  PUBLISHED: "Published by you",
  CANCELLED: "Stopped",
};

export function stageLabel(state: string): string {
  return STAGE_LABELS[state] ?? state.replaceAll("_", " ").toLowerCase();
}

/** How far along the pipeline a campaign is, as `[step, total]`. */
export function stageProgress(state: string): [number, number] {
  const index = (HAPPY_PATH as readonly string[]).indexOf(state);
  return [index < 0 ? 0 : index + 1, HAPPY_PATH.length];
}

/** Whether a campaign is waiting on the owner rather than on a job. */
export function needsOwner(state: string): boolean {
  return ["IDEA_REVIEW", "ART_REVIEW", "LISTING_REVIEW"].includes(state);
}

/** Pull the human-readable message out of an RFC 9457 problem response. */
export function problemDetail(err: unknown): string | null {
  const data = (err as { data?: { detail?: unknown } } | null)?.data;
  return typeof data?.detail === "string" ? data.detail : null;
}

function csrfHeaders(): Record<string, string> {
  if (typeof document === "undefined") return {};
  const match = `; ${document.cookie}`.split("; etsy_csrf=");
  const token = match.length === 2 ? match.pop()?.split(";").shift() : null;
  return token ? { "x-csrf-token": token } : {};
}

/** Used only when the API gives no problem detail of its own. */
const FALLBACK_ERRORS: Record<string, string> = {
  cancel: "Could not stop this campaign.",
  rerun: "Could not rerun this campaign.",
  delete: "Could not delete this campaign.",
};

export function useWorkflowControls(apiBase: string, onDone: () => Promise<void> | void) {
  const controlError = ref<string | null>(null);
  const pendingWorkflowId = ref<string | null>(null);

  /**
   * The backend refuses the action when the state moved on since the page last
   * polled, so its problem detail is what the owner sees rather than a guess.
   */
  async function controlWorkflow(
    id: string,
    action: "cancel" | "rerun" | "delete",
    options?: { fromScratch?: boolean },
  ): Promise<boolean> {
    pendingWorkflowId.value = id;
    controlError.value = null;
    const base = `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${id}`;
    let url = action === "delete" ? base : `${base}/${action}`;
    if (action === "rerun" && options?.fromScratch) {
      url += "?from_scratch=true";
    }
    try {
      await $fetch(url, {
        method: action === "delete" ? "DELETE" : "POST",
        credentials: "include",
        headers: csrfHeaders(),
      });
      await onDone();
      return true;
    } catch (err) {
      controlError.value = problemDetail(err) ?? FALLBACK_ERRORS[action];
      return false;
    } finally {
      pendingWorkflowId.value = null;
    }
  }

  return { controlError, pendingWorkflowId, controlWorkflow };
}
