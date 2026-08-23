/**
 * Centralized display label formatters for user-facing UI.
 * Maps internal technical enums, gates, and statuses to friendly product terms.
 */

export const WORKFLOW_STAGE_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  RESEARCH_QUEUED: "Research Queued",
  RESEARCHING: "Researching",
  IDEA_REVIEW: "Review Concepts",
  IDEA_APPROVED: "Concept Approved",
  ART_QUEUED: "Artwork Queued",
  ART_GENERATION: "Generating Artwork",
  ART_REVIEW: "Review Artwork",
  ARTWORK_APPROVED: "Artwork Approved",
  PRODUCTION: "Production & Mockups",
  IP_REVIEW: "IP & Trademark Review",
  LISTING_REVIEW: "Review Listing",
  READY_FOR_ETSY_DRAFT: "Ready for Etsy",
  ETSY_DRAFT_CREATED: "Draft Created",
  ETSY_DRAFT_FAILED: "Draft Failed",
  PUBLISHED: "Published",
  CANCELLED: "Stopped",
};

export const APPROVAL_ACTION_LABELS: Record<string, string> = {
  IDEA_APPROVAL: "Approve Concept",
  ARTWORK_APPROVAL: "Approve Artwork",
  LISTING_APPROVAL: "Approve Listing",
};

export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  recraft: "Recraft",
  gemini: "Google Gemini",
  openai: "OpenAI",
  tavily: "Tavily",
  etsy: "Etsy",
  printful: "Printful",
};

export function formatWorkflowStage(state: string): string {
  if (!state) return "";
  return WORKFLOW_STAGE_LABELS[state] ?? state.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatApprovalAction(gate: string): string {
  if (!gate) return "";
  return APPROVAL_ACTION_LABELS[gate] ?? "Approve";
}

export function formatProviderName(provider: string): string {
  if (!provider) return "";
  return PROVIDER_DISPLAY_NAMES[provider.toLowerCase()] ?? provider;
}

/**
 * Clean and sanitize error messages for end users.
 * Removes internal class names, stack traces, and technical gate exception text.
 */
export function sanitizeUserErrorMessage(rawError: unknown, fallback: string = "An unexpected error occurred. Please try again."): string {
  if (!rawError) return fallback;
  let msg = fallback;
  if (typeof rawError === "string") {
    msg = rawError;
  } else if (typeof rawError === "object" && rawError !== null) {
    const errObj = rawError as Record<string, unknown>;
    const dataObj = errObj.data as Record<string, unknown> | undefined;
    msg = String(dataObj?.detail || errObj.message || fallback);
  }


  // Map spending cap / quota exhaustion errors
  if (msg.toLowerCase().includes("spending cap") || msg.toLowerCase().includes("quota exceeded") || msg.toLowerCase().includes("resource_exhausted")) {
    return "Your Gemini API monthly spending cap or quota is exhausted. Please check https://ai.studio/spend or update your API key in Settings.";
  }

  // Map internal gate errors
  if (msg.includes("requires gate IDEA_APPROVAL") || msg.includes("gate-not-approved")) {
    return "Please approve the concept before proceeding.";
  }
  if (msg.includes("requires gate ARTWORK_APPROVAL")) {
    return "Please approve an artwork design before proceeding.";
  }
  if (msg.includes("requires gate LISTING_APPROVAL")) {
    return "Please complete the listing review before proceeding.";
  }
  if (msg.includes("GateNotSatisfiedError") || msg.includes("cannot be decided while")) {
    return "This milestone is not ready for review yet.";
  }
  if (msg.includes("ProviderError") || msg.includes("RETRYABLE")) {
    return "Temporary service error. Please try again in a moment.";
  }
  if (msg.includes("SQL") || msg.includes("database") || msg.includes("redis") || msg.includes("MinIO")) {
    return fallback;
  }

  return msg;
}
