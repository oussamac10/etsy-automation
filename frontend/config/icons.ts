/**
 * Centralized Lucide icon mapping for Etsy PNG Automation frontend.
 * Provides standard, accessible icon names across all pages and components.
 */

export const icons = {
  // Navigation & Core App
  dashboard: "lucide:layout-dashboard",
  campaigns: "lucide:palette",
  createCampaign: "lucide:plus",
  settings: "lucide:settings",
  externalLink: "lucide:external-link",
  close: "lucide:x",
  menu: "lucide:menu",

  // Campaign Modes
  discover: "lucide:search",
  idea: "lucide:lightbulb",
  hybrid: "lucide:git-merge",

  // Stage 1: Research & Concepts
  research: "lucide:search-check",
  marketSignals: "lucide:trending-up",
  ai: "lucide:sparkles",
  keywords: "lucide:tags",
  score: "lucide:gauge",
  confidence: "lucide:badge-check",
  risk: "lucide:shield-alert",
  safe: "lucide:shield-check",
  prompt: "lucide:file-text",
  editPrompt: "lucide:pencil",
  approve: "lucide:circle-check",
  reject: "lucide:circle-x",

  // Stage 2: Artwork Studio
  artwork: "lucide:image",
  generateArtwork: "lucide:wand-sparkles",
  regenerate: "lucide:refresh-cw",
  refine: "lucide:sliders-horizontal",

  // Stage 3: PNG Production & Mockups
  production: "lucide:file-image",
  transparency: "lucide:layers",
  upscale: "lucide:maximize",
  typography: "lucide:type",
  qa: "lucide:clipboard-check",
  mockups: "lucide:images",
  download: "lucide:download",
  palette: "lucide:palette",
  move: "lucide:move",
  preview: "lucide:eye",

  // Products
  tshirt: "lucide:shirt",
  sweatshirt: "lucide:shirt",
  toteBag: "lucide:shopping-bag",
  mug: "lucide:coffee",
  tumbler: "lucide:cup-soda",
  poster: "lucide:image",
  sticker: "lucide:tags",
  phoneCase: "lucide:smartphone",
  candle: "lucide:flame",

  // Integrations & Settings
  telegram: "lucide:send",
  apiKey: "lucide:key-round",
  budget: "lucide:wallet-cards",
  cost: "lucide:circle-dollar-sign",
  etsy: "lucide:store",
  seo: "lucide:search",
  listing: "lucide:file-text",

  // Controls & Lifecycle Actions
  delete: "lucide:trash-2",
  stop: "lucide:square",
  pause: "lucide:pause",
  resume: "lucide:play",
  retry: "lucide:rotate-ccw",
  back: "lucide:arrow-left",

  // Status & Feedback
  success: "lucide:circle-check",
  warning: "lucide:triangle-alert",
  error: "lucide:circle-alert",
  info: "lucide:info",
  loading: "lucide:loader-circle",
  clock: "lucide:clock-3",
  cancelled: "lucide:ban",
} as const;

export type IconKey = keyof typeof icons;

/**
 * Returns the standard Lucide icon name for a given product type.
 */
export function getProductIcon(productType: string): string {
  const norm = productType.toLowerCase().replace(/[- ]/g, "_");
  if (norm.includes("mug") || norm.includes("cup")) return icons.mug;
  if (norm.includes("sweatshirt") || norm.includes("hoodie") || norm.includes("crewneck")) return icons.sweatshirt;
  if (norm.includes("tshirt") || norm.includes("t_shirt") || norm.includes("shirt") || norm.includes("tee")) return icons.tshirt;
  if (norm.includes("tote") || norm.includes("bag")) return icons.toteBag;
  if (norm.includes("tumbler")) return icons.tumbler;
  if (norm.includes("poster") || norm.includes("wall_art")) return icons.poster;
  if (norm.includes("sticker")) return icons.sticker;
  if (norm.includes("phone")) return icons.phoneCase;
  if (norm.includes("candle")) return icons.candle;
  return icons.artwork;
}

/**
 * Returns the standard Lucide icon name for a given workflow state.
 */
export function getWorkflowStateIcon(state: string): string {
  switch (state) {
    case "INITIAL":
    case "PENDING":
    case "QUEUED":
      return icons.clock;
    case "RESEARCHING":
    case "PROMPTING":
    case "GENERATING_ARTWORK":
    case "REFINING_ARTWORK":
    case "PRODUCING_MASTER":
    case "GENERATING_MOCKUPS":
      return icons.loading;
    case "IDEA_REVIEW":
    case "CONCEPT_SELECTED":
      return icons.idea;
    case "ARTWORK_REVIEW":
      return icons.artwork;
    case "ARTWORK_APPROVED":
    case "PRODUCTION_READY":
      return icons.production;
    case "COMPLETE":
    case "LISTING_PUBLISHED":
      return icons.success;
    case "PAUSED":
      return icons.pause;
    case "FAILED":
    case "RESEARCH_FAILED":
    case "ARTWORK_FAILED":
    case "PRODUCTION_FAILED":
      return icons.error;
    case "CANCELLED":
      return icons.cancelled;
    default:
      return icons.info;
  }
}
