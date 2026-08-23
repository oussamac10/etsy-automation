<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from "vue";
import {
  isRunning,
  isStopped,
  needsOwner,
  problemDetail,
  stageLabel,
  stageProgress,
  useWorkflowControls,
} from "~/composables/useWorkflowControls";

import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Textarea from "~/components/ui/Textarea.vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import CustomizableSelect, { type SelectOption } from "~/components/ui/CustomizableSelect.vue";
import Pagination from "~/components/ui/Pagination.vue";
import Progress from "~/components/ui/Progress.vue";
import { useLibraryProducts } from "~/composables/useLibraryProducts";

const { libraryProductOptions, fetchLibraryProducts } = useLibraryProducts();


const BUYER_OPTIONS: SelectOption[] = [
  { value: "coffee lovers", label: "Coffee Lovers & Baristas", icon: "lucide:coffee" },
  { value: "teachers", label: "Teachers & Educators", icon: "lucide:graduation-cap" },
  { value: "dog lovers", label: "Dog Moms & Pet Parents", icon: "lucide:paw-print" },
  { value: "plant lovers", label: "Plant Enthusiasts & Botanists", icon: "lucide:sprout" },
  { value: "book lovers", label: "Bookworms & Readers", icon: "lucide:book-open" },
  { value: "campers & hikers", label: "Outdoor Campers & Hikers", icon: "lucide:tent" },
  { value: "nurses", label: "Nurses & Healthcare", icon: "lucide:heart-pulse" },
  { value: "moms", label: "Mothers & New Moms", icon: "lucide:heart" },
  { value: "dads", label: "Fathers & Dads", icon: "lucide:user" },
  { value: "gamers", label: "Gamers & Techies", icon: "lucide:gamepad-2" },
  { value: "crafters", label: "Crafters & DIYers", icon: "lucide:palette" },
  { value: "minimalists", label: "Minimalists & Modernists", icon: "lucide:sparkles" },
];

const NICHE_OPTIONS: SelectOption[] = [
  { value: "retro camping", label: "Retro Camping & Wilderness", icon: "lucide:tent" },
  { value: "black cats", label: "Black Cats & Witchy", icon: "lucide:sparkles" },
  { value: "cottagecore", label: "Cottagecore & Mushrooms", icon: "lucide:sprout" },
  { value: "vintage floral", label: "Vintage Botanical & Floral", icon: "lucide:flower-2" },
  { value: "cozy coffee", label: "Cozy Coffee & Books", icon: "lucide:coffee" },
  { value: "space celestial", label: "Space & Celestial Stars", icon: "lucide:moon" },
  { value: "punny food", label: "Punny Food & Cooking", icon: "lucide:utensils" },
  { value: "golden retriever", label: "Golden Retrievers & Dogs", icon: "lucide:paw-print" },
  { value: "desert cacti", label: "Desert & Southwest Cacti", icon: "lucide:sun" },
  { value: "coastal ocean", label: "Coastal & Ocean Waves", icon: "lucide:waves" },
];

const STYLE_OPTIONS: SelectOption[] = [
  { value: "watercolor", label: "Soft Watercolor & Wash", icon: "lucide:palette" },
  { value: "minimalist line art", label: "Minimalist Line Art & Monoline", icon: "lucide:pen-tool" },
  { value: "vintage retro 70s", label: "Vintage 70s / Retro Distressed", icon: "lucide:radio" },
  { value: "boho botanical", label: "Boho Botanical & Earthy", icon: "lucide:leaf" },
  { value: "kawaii cute", label: "Cute Kawaii & Pastel", icon: "lucide:sparkles" },
  { value: "bold typography", label: "Bold Typography & Lettering", icon: "lucide:type" },
  { value: "engraving woodcut", label: "Engraving & Woodcut Vintage", icon: "lucide:feather" },
  { value: "pixel art", label: "8-Bit / 16-Bit Pixel Art", icon: "lucide:grid" },
  { value: "geometric vector", label: "Geometric Clean Vector", icon: "lucide:shapes" },
  { value: "oil painting", label: "Classic Oil Painting Impressionist", icon: "lucide:brush" },
];

const OCCASION_OPTIONS: SelectOption[] = [
  { value: "birthday", label: "Birthday", icon: "lucide:cake" },
  { value: "christmas", label: "Christmas & Holiday", icon: "lucide:gift" },
  { value: "halloween", label: "Halloween & Fall", icon: "lucide:ghost" },
  { value: "valentines", label: "Valentine's Day", icon: "lucide:heart" },
  { value: "mothers day", label: "Mother's Day", icon: "lucide:heart-handshake" },
  { value: "fathers day", label: "Father's Day", icon: "lucide:award" },
  { value: "graduation", label: "Graduation", icon: "lucide:graduation-cap" },
  { value: "wedding", label: "Wedding & Anniversary", icon: "lucide:gem" },
  { value: "thanksgiving", label: "Thanksgiving", icon: "lucide:utensils" },
  { value: "baby shower", label: "Baby Shower & Newborn", icon: "lucide:smile" },
  { value: "summer vacation", label: "Summer Vacation & Travel", icon: "lucide:palmtree" },
  { value: "everyday", label: "Everyday / No Special Occasion", icon: "lucide:sparkles" },
];

const SEASON_OPTIONS: SelectOption[] = [
  { value: "winter", label: "Winter", icon: "lucide:snowflake" },
  { value: "spring", label: "Spring", icon: "lucide:flower" },
  { value: "summer", label: "Summer", icon: "lucide:sun" },
  { value: "autumn", label: "Autumn / Fall", icon: "lucide:leaf" },
  { value: "evergreen", label: "Year-Round / Evergreen", icon: "lucide:trees" },
];

interface Workflow {
  id: string;
  name: string;
  idea_mode: string;
  target_marketplace: string;
  target_country: string;
  output_language: string;
  target_buyer: string | null;
  intended_product_uses: string[];
  state: string;
  version: number;
  created_at: string;
  updated_at: string;
  shop_section_id?: string | null;
  shop_section_name?: string | null;
}

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

const workflows = ref<Workflow[]>([]);
const isListLoading = ref(true);
const listError = ref<string | null>(null);

// Form state
const showCreateForm = ref(false);
const ideaMode = ref<"market-led" | "user-idea" | "hybrid">("market-led");
const workflowName = ref("");
const targetCountry = ref("US");
const outputLanguage = ref("en");
const targetMarketplace = ref("etsy");
const targetBuyer = ref<string[]>([]);
const intendedProductUses = ref<string[]>(["mug"]);
const isCreating = ref(false);
const creationError = ref<string | null>(null);

// Original Idea fields (for user-idea/hybrid modes)
const originalText = ref("");
const slogan = ref("");
const desiredStyle = ref<string[]>([]);
const audience = ref<string[]>([]);
const occasion = ref<string[]>([]);
const season = ref<string[]>([]);
const preferredNiche = ref<string[]>([]);

// Clear inapplicable fields when mode changes to prevent stale data submission
watch(ideaMode, (newMode) => {
  if (newMode === "market-led") {
    originalText.value = "";
    slogan.value = "";
    desiredStyle.value = [];
    audience.value = [];
    occasion.value = [];
    season.value = [];
  } else {
    preferredNiche.value = [];
  }
});

// Filter state
const searchQuery = ref("");
const selectedFilter = ref<"all" | "active" | "needs-review" | "completed">("all");
const selectedSection = ref<string>("all");

const availableSections = computed(() => {
  const set = new Set<string>();
  for (const wf of workflows.value) {
    if (wf.shop_section_name?.trim()) {
      set.add(wf.shop_section_name.trim());
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const sectionCounts = computed(() => {
  const counts: Record<string, number> = {};
  for (const wf of workflows.value) {
    const sec = wf.shop_section_name?.trim() || "unassigned";
    counts[sec] = (counts[sec] || 0) + 1;
  }
  return counts;
});

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

async function loadWorkflows(): Promise<void> {
  isListLoading.value = workflows.value.length === 0;
  listError.value = null;
  try {
    const data = await $fetch<{ items: Workflow[] }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows`,
      { credentials: "include" }
    );
    workflows.value = data.items;
  } catch {
    listError.value = "Failed to load workflows. Please ensure you are logged in.";
  } finally {
    isListLoading.value = false;
  }
}

async function handleCreateWorkflow(): Promise<void> {
  isCreating.value = true;
  creationError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    let resolvedName = workflowName.value.trim();
    if (!resolvedName && ideaMode.value === "market-led") {
      const monthYear = new Date().toLocaleString("en-US", { month: "short", year: "numeric" });
      if (preferredNiche.value.length > 0) {
        resolvedName = `${targetCountry.value.toUpperCase()} Trend Discovery (${preferredNiche.value.join(", ")}) - ${monthYear}`;
      } else {
        resolvedName = `${targetCountry.value.toUpperCase()} Trend Discovery - ${monthYear}`;
      }
    }

    if (ideaMode.value !== "market-led" && !resolvedName) {
      creationError.value = "Failed to create workflow: Campaign Name is required.";
      isCreating.value = false;
      return;
    }

    // Step 1: Create the workflow
    const payload = {
      idea_mode: ideaMode.value,
      name: resolvedName,
      target_country: targetCountry.value.trim(),
      output_language: outputLanguage.value.trim(),
      target_marketplace: targetMarketplace.value.trim(),
      target_buyer: targetBuyer.value.length > 0 ? targetBuyer.value.join(", ") : null,
      intended_product_uses: intendedProductUses.value,
    };

    let newWorkflow: Workflow;
    try {
      newWorkflow = await $fetch<Workflow>(
        `${apiBase.replace(/\/$/, "")}/api/v1/workflows`,
        {
          method: "POST",
          headers,
          body: payload,
          credentials: "include",
        }
      );
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string } };
      const detail = errorObj.data?.detail || "Failed to create workflow.";
      creationError.value = `Failed to create workflow: ${detail}`;
      isCreating.value = false;
      return;
    }

    // Step 2: If user-idea or hybrid, submit original idea
    if (ideaMode.value !== "market-led") {
      const ideaPayload = {
        original_text: originalText.value.trim(),
        slogan: slogan.value.trim() || null,
        desired_style: desiredStyle.value.length > 0 ? desiredStyle.value.join(", ") : null,
        audience: audience.value.length > 0 ? audience.value.join(", ") : null,
        occasion: occasion.value.length > 0 ? occasion.value.join(", ") : null,
        season: season.value.length > 0 ? season.value.join(", ") : null,
        product_uses: intendedProductUses.value,
      };

      try {
        await $fetch(
          `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${newWorkflow.id}/ideas`,
          {
            method: "POST",
            headers,
            body: ideaPayload,
            credentials: "include",
          }
        );
      } catch (err: unknown) {
        const errorObj = err as { data?: { detail?: string } };
        const detail = errorObj.data?.detail || "Failed to save idea.";
        creationError.value = `Failed to save idea: ${detail}`;
        isCreating.value = false;
        return;
      }
    }

    // Step 3: Trigger background research
    try {
      await $fetch(
        `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${newWorkflow.id}/research`,
        {
          method: "POST",
          headers,
          credentials: "include",
        }
      );
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string } };
      const detail = errorObj.data?.detail || "Failed to start research.";
      creationError.value = `Failed to start research: ${detail}`;
      isCreating.value = false;
      return;
    }

    // Reset form and reload
    showCreateForm.value = false;
    workflowName.value = "";
    targetBuyer.value = [];
    intendedProductUses.value = ["mug"];
    originalText.value = "";
    slogan.value = "";
    desiredStyle.value = [];
    audience.value = [];
    occasion.value = [];
    season.value = [];
    preferredNiche.value = [];

    await loadWorkflows();
  } catch (err) {
    creationError.value = problemDetail(err) ?? "Could not create this campaign.";
  } finally {
    isCreating.value = false;
  }
}

const { controlError, pendingWorkflowId, controlWorkflow } = useWorkflowControls(
  apiBase,
  loadWorkflows
);

// Metrics
const totalCount = computed(() => workflows.value.length);
const runningCount = computed(() => workflows.value.filter((wf) => isRunning(wf.state)).length);
const attentionCount = computed(() => workflows.value.filter((wf) => needsOwner(wf.state)).length);
const completedCount = computed(() =>
  workflows.value.filter((wf) => wf.state === "LISTING_APPROVED" || wf.state === "COMPLETED").length
);

const filteredWorkflows = computed(() => {
  let list = workflows.value;
  if (selectedFilter.value === "active") {
    list = list.filter((wf) => isRunning(wf.state));
  } else if (selectedFilter.value === "needs-review") {
    list = list.filter((wf) => needsOwner(wf.state));
  } else if (selectedFilter.value === "completed") {
    list = list.filter((wf) => wf.state === "LISTING_APPROVED" || wf.state === "COMPLETED");
  }

  if (selectedSection.value !== "all") {
    if (selectedSection.value === "unassigned") {
      list = list.filter((wf) => !wf.shop_section_name?.trim());
    } else {
      list = list.filter(
        (wf) => wf.shop_section_name?.trim().toLowerCase() === selectedSection.value.toLowerCase()
      );
    }
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter(
      (wf) =>
        wf.name.toLowerCase().includes(q) ||
        wf.idea_mode.toLowerCase().includes(q) ||
        wf.target_country.toLowerCase().includes(q) ||
        (wf.shop_section_name && wf.shop_section_name.toLowerCase().includes(q))
    );
  }
  return list;
});

// Pagination state (Max 20 per page)
const currentPage = ref(1);
const pageSize = 20;
const totalFilteredWorkflows = computed(() => filteredWorkflows.value.length);
const paginatedWorkflows = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredWorkflows.value.slice(start, start + pageSize);
});

watch([selectedFilter, selectedSection, searchQuery], () => {
  currentPage.value = 1;
});

const hasActiveWorkflows = computed(() => workflows.value.some((wf) => isRunning(wf.state)));

let pollInterval: ReturnType<typeof setInterval> | null = null;

function startPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(loadWorkflows, 5000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

watch(hasActiveWorkflows, (active) => {
  if (active) {
    startPolling();
  } else {
    stopPolling();
  }
});

onMounted(async () => {
  try {
    await Promise.all([
      loadWorkflows(),
      fetchLibraryProducts(),
    ]);
  } catch {
    // Non-blocking fallback if offline
    await Promise.all([loadWorkflows(), fetchLibraryProducts()]);
  }
  if (hasActiveWorkflows.value) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="min-h-screen bg-background pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Dashboard Hero Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-border pb-8">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <Icon name="lucide:sparkles" class="size-4" aria-hidden="true" />
            <span>Digital Product Automation</span>
          </div>
          <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Etsy PNG Automation
          </h1>
          <p class="text-sm text-muted-foreground max-w-2xl">
            Autonomous research-to-draft engine for high-resolution digital products. Human review and approval at every milestone.
          </p>
        </div>


        <div class="flex items-center gap-3">
          <Button
            v-if="!showCreateForm"
            variant="default"
            size="lg"
            class="shadow-md shadow-primary/20 gap-2 font-semibold cursor-pointer inline-flex items-center"
            @click="showCreateForm = true"
          >
            <Icon name="lucide:plus" class="size-4" aria-hidden="true" />
            <span>Create New Campaign</span>
          </Button>
          <Button
            v-else
            variant="outline"
            size="lg"
            class="font-semibold cursor-pointer"
            @click="showCreateForm = false"
          >
            Cancel Creation
          </Button>
        </div>
      </div>

      <!-- Top KPI Stats Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total Campaigns</span>
            <Icon name="lucide:layers" class="size-4 text-muted-foreground" aria-hidden="true" />
          </div>
          <p class="text-2xl font-bold text-foreground mt-2">{{ totalCount }}</p>
          <span class="text-[11px] text-muted-foreground">All registered workflows</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-amber-600 uppercase tracking-wide">In Progress</span>
            <Icon
              name="lucide:loader-circle"
              class="size-4"
              :class="runningCount > 0 ? 'text-amber-600 animate-spin' : 'text-amber-600/50'"
              aria-hidden="true"
            />
          </div>
          <p class="text-2xl font-bold text-amber-600 mt-2">{{ runningCount }}</p>
          <span class="text-[11px] text-amber-600/80">Active background tasks</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-primary uppercase tracking-wide">Needs Review</span>
            <Icon name="lucide:clock-3" class="size-4 text-primary" aria-hidden="true" />
          </div>
          <p class="text-2xl font-bold text-primary mt-2">{{ attentionCount }}</p>
          <span class="text-[11px] text-primary/80">Awaiting human sign-off</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-emerald-600 uppercase tracking-wide">Approved / Complete</span>
            <Icon name="lucide:circle-check" class="size-4 text-emerald-600" aria-hidden="true" />
          </div>
          <p class="text-2xl font-bold text-emerald-600 mt-2">{{ completedCount }}</p>
          <span class="text-[11px] text-emerald-600/80">Ready for listing</span>
        </Card>
      </div>

      <!-- Campaign Creation Card -->
      <Card v-if="showCreateForm" class="shadow-lg border-border bg-gradient-to-b from-white to-slate-50/50">
        <CardHeader class="pb-4">
          <div class="flex items-center gap-2.5">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-primary border border-border">
              <Icon name="lucide:sparkles" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <CardTitle class="text-xl">Start a New Design Campaign</CardTitle>
              <CardDescription>Configure market targeting, choose an input mode, and kick off AI synthesis</CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <Alert v-if="creationError" variant="destructive" class="mb-6">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertDescription>{{ creationError }}</AlertDescription>
          </Alert>

          <form class="space-y-6" @submit.prevent="handleCreateWorkflow">
            <!-- Step 1: Mode Selection Cards -->
            <div class="space-y-3">
              <Label>Select Design Input Mode</Label>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Mode 1: Market Led -->
                <div
                  :class="[
                    'relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-150',
                    ideaMode === 'market-led'
                      ? 'border-primary bg-primary/10 shadow-2xs'
                      : 'border-border bg-card hover:border-primary/40 hover:bg-secondary/60',
                  ]"
                  @click="ideaMode = 'market-led'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Icon name="lucide:search" class="size-4 text-primary" aria-hidden="true" />
                      <span class="font-bold text-sm text-foreground">Discover Ideas</span>
                    </div>
                    <Badge v-if="ideaMode === 'market-led'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-primary mb-1">Market-Led Discovery</p>
                  <p class="text-xs text-muted-foreground leading-relaxed">
                    Find 3 design opportunities based on current demand, competition, trends, seasonal timing, and buyer intent.
                  </p>
                </div>

                <!-- Mode 2: User Idea -->
                <div
                  :class="[
                    'relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-150',
                    ideaMode === 'user-idea'
                      ? 'border-primary bg-primary/10 shadow-2xs'
                      : 'border-border bg-card hover:border-primary/40 hover:bg-secondary/60',
                  ]"
                  @click="ideaMode = 'user-idea'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Icon name="lucide:lightbulb" class="size-4 text-primary" aria-hidden="true" />
                      <span class="font-bold text-sm text-foreground">Use My Idea</span>
                    </div>
                    <Badge v-if="ideaMode === 'user-idea'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-primary mb-1">Idea Optimization</p>
                  <p class="text-xs text-muted-foreground leading-relaxed">
                    Provide your own theme or slogan. The engine refines keywords, prompts, and target appeal.
                  </p>
                </div>

                <!-- Mode 3: Hybrid -->
                <div
                  :class="[
                    'relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-150',
                    ideaMode === 'hybrid'
                      ? 'border-primary bg-primary/10 shadow-2xs'
                      : 'border-border bg-card hover:border-primary/40 hover:bg-secondary/60',
                  ]"
                  @click="ideaMode = 'hybrid'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Icon name="lucide:git-merge" class="size-4 text-primary" aria-hidden="true" />
                      <span class="font-bold text-sm text-foreground">Hybrid Approach</span>
                    </div>
                    <Badge v-if="ideaMode === 'hybrid'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-primary mb-1">Direction + Signals</p>
                  <p class="text-xs text-muted-foreground leading-relaxed">
                    Combine your creative direction with real-time market data to create derived variations.
                  </p>
                </div>
              </div>
            </div>

            <!-- Step 2: Campaign Settings -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <Label for="campaign-name" :required="ideaMode !== 'market-led'">
                  Campaign Name
                </Label>
                <Input
                  id="campaign-name"
                  v-model="workflowName"
                  :required="ideaMode !== 'market-led'"
                  :placeholder="ideaMode === 'market-led' ? 'e.g. US Trend Discovery - Aug 2026' : 'e.g. Autumn Mugs 2026'"
                />
                <span v-if="ideaMode === 'market-led'" class="text-[11px] text-muted-foreground">
                  Optional — auto-generates if left blank
                </span>
              </div>

              <div class="space-y-1.5">
                <Label for="target-country">Target Marketplace Country</Label>
                <select
                  id="target-country"
                  v-model="targetCountry"
                  class="flex h-9 w-full rounded-md border border-border bg-card px-3 py-1 text-sm text-foreground shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <option value="US">United States (US)</option>
                  <option value="CA">Canada (CA)</option>
                  <option value="GB">United Kingdom (GB)</option>
                  <option value="AU">Australia (AU)</option>
                </select>
              </div>
            </div>

            <!-- Optional Targeting Filters -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="space-y-1.5">
                <Label for="output-language">Output Language</Label>
                <Input id="output-language" v-model="outputLanguage" required />
              </div>

              <div class="space-y-1.5">
                <Label for="target-buyer">Buyer Persona (Optional)</Label>
                <CustomizableSelect
                  id="target-buyer"
                  v-model="targetBuyer"
                  :options="BUYER_OPTIONS"
                  storage-key="etsy_custom_buyers"
                  :is-multi="true"
                  placeholder="Select or type buyers..."
                />
              </div>

              <div v-if="ideaMode === 'market-led'" class="space-y-1.5">
                <Label for="preferred-niche">Preferred Niche (Optional)</Label>
                <CustomizableSelect
                  id="preferred-niche"
                  v-model="preferredNiche"
                  :options="NICHE_OPTIONS"
                  storage-key="etsy_custom_niches"
                  :is-multi="true"
                  placeholder="Select or type niches..."
                />
              </div>

              <div :class="ideaMode !== 'market-led' ? 'md:col-span-1 lg:col-span-2' : ''" class="space-y-1.5">
                <div class="flex items-center justify-between">
                  <Label for="product-uses">Intended Physical Products</Label>
                  <NuxtLink
                    to="/library"
                    class="p-0.5 rounded text-muted-foreground hover:text-primary hover:bg-secondary transition-colors"
                    title="Manage Mockup Library"
                  >
                    <Icon name="lucide:folder-cog" class="size-3.5" aria-hidden="true" />
                  </NuxtLink>
                </div>
                <CustomizableSelect
                  id="product-uses"
                  v-model="intendedProductUses"
                  :options="libraryProductOptions"
                  :allow-custom="false"
                  :is-multi="true"
                  placeholder="Select products from library..."
                />
              </div>
            </div>

            <!-- Step 3: Wording / Brief inputs (for user-idea/hybrid modes) -->
            <div v-if="ideaMode !== 'market-led'" class="border-t border-border pt-6 space-y-4">
              <h3 class="text-base font-bold text-foreground">
                {{ ideaMode === 'hybrid' ? 'Your Theme / Direction Details' : 'Your Design Idea Details' }}
              </h3>

              <div class="space-y-1.5">
                <Label for="original-text" required>
                  {{ ideaMode === 'hybrid' ? 'Theme / Direction Brief' : 'Idea Brief / Prompt Wording' }}
                </Label>
                <Textarea
                  id="original-text"
                  v-model="originalText"
                  required
                  :rows="3"
                  :placeholder="
                    ideaMode === 'hybrid'
                      ? 'e.g. retro camping theme for outdoorsy adults, warm colors, humorous but not childish'
                      : 'Detail the subject, elements, colors, and layout you want (minimum 3 characters)'
                  "
                />
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-1.5">
                  <Label for="desired-style">
                    {{ ideaMode === 'hybrid' ? 'Preferred Style (Optional)' : 'Desired Style (Optional)' }}
                  </Label>
                  <CustomizableSelect
                    id="desired-style"
                    v-model="desiredStyle"
                    :options="STYLE_OPTIONS"
                    storage-key="etsy_custom_styles"
                    :is-multi="true"
                    placeholder="Select or type styles..."
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="slogan">Exact Slogan / Typography (Optional)</Label>
                  <Input id="slogan" v-model="slogan" placeholder="e.g. BUT FIRST COFFEE" />
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="space-y-1.5">
                  <Label for="audience">Audience (Optional)</Label>
                  <CustomizableSelect
                    id="audience"
                    v-model="audience"
                    :options="BUYER_OPTIONS"
                    storage-key="etsy_custom_audiences"
                    :is-multi="true"
                    placeholder="Select or type audiences..."
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="occasion">Occasion (Optional)</Label>
                  <CustomizableSelect
                    id="occasion"
                    v-model="occasion"
                    :options="OCCASION_OPTIONS"
                    storage-key="etsy_custom_occasions"
                    :is-multi="true"
                    placeholder="Select or type occasions..."
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="season">Season (Optional)</Label>
                  <CustomizableSelect
                    id="season"
                    v-model="season"
                    :options="SEASON_OPTIONS"
                    storage-key="etsy_custom_seasons"
                    :is-multi="true"
                    placeholder="Select or type seasons..."
                  />
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between border-t border-border pt-4">
              <div class="flex items-center gap-2 text-xs text-muted-foreground">
                <Icon name="lucide:clock" class="size-4 text-primary shrink-0" aria-hidden="true" />
                <span>Runs in background · Pauses for concept review</span>
              </div>

              <Button
                type="submit"
                variant="default"
                size="lg"
                :loading="isCreating"
                class="shadow-md shadow-primary/20 font-bold cursor-pointer inline-flex items-center"
              >
                <span>
                  {{
                    ideaMode === 'market-led' ? 'Find 3 Opportunities' :
                    ideaMode === 'user-idea' ? 'Research My Idea' :
                    'Generate Variations'
                  }}
                </span>
                <Icon v-if="!isCreating" name="lucide:arrow-right" class="size-4 ml-1" aria-hidden="true" />
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <!-- Active Workflows List Card -->
      <Card class="shadow-2xs">
        <CardHeader class="pb-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <CardTitle class="text-xl">Your Design Workflows</CardTitle>
              <CardDescription>Track campaign execution, review milestones, and manage drafts</CardDescription>
            </div>

            <!-- Search & Filters -->
            <div class="flex items-center gap-2 flex-wrap">
              <!-- Section Filter Dropdown -->
              <div v-if="availableSections.length > 0" class="flex items-center gap-1.5">
                <select
                  v-model="selectedSection"
                  class="h-8 rounded-lg border border-border bg-background px-2.5 py-1 text-xs text-foreground shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
                  aria-label="Filter by Shop Section"
                >
                  <option value="all">All Sections ({{ totalCount }})</option>
                  <option v-for="sec in availableSections" :key="sec" :value="sec">
                    {{ sec }} ({{ sectionCounts[sec] || 0 }})
                  </option>
                  <option v-if="sectionCounts['unassigned']" value="unassigned">
                    No Section ({{ sectionCounts['unassigned'] }})
                  </option>
                </select>
              </div>

              <div class="relative w-48 sm:w-60">
                <Input
                  v-model="searchQuery"
                  placeholder="Search campaigns, sections..."
                  class="pl-8 text-xs h-8"
                />
                <Icon name="lucide:search" class="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground pointer-events-none" aria-hidden="true" />
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent class="pt-0">
          <Alert v-if="controlError" variant="destructive" class="mb-4">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertDescription>{{ controlError }}</AlertDescription>
          </Alert>

          <div v-if="isListLoading" class="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
            <Icon name="lucide:loader-circle" class="size-6 animate-spin text-primary" aria-hidden="true" />
            <p class="text-sm font-medium">Loading campaigns...</p>
          </div>

          <Alert v-else-if="listError" variant="warning" class="mb-4">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertDescription>{{ listError }}</AlertDescription>
          </Alert>

          <!-- Empty State -->
          <div v-else-if="filteredWorkflows.length === 0" class="text-center py-16 px-4">
            <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary text-primary mb-4 border border-border shadow-2xs">
              <Icon name="lucide:sparkles" class="size-7" aria-hidden="true" />
            </div>
            <h3 class="text-base font-bold text-foreground mb-1">
              {{ searchQuery ? 'No matching campaigns' : 'No active campaigns' }}
            </h3>
            <p class="text-muted-foreground text-xs mb-6 max-w-sm mx-auto">
              {{ searchQuery ? 'Try adjusting your search query or clear filters.' : 'Get started by creating your first product design workflow with automated research.' }}
            </p>
            <Button
              v-if="!searchQuery"
              variant="default"
              size="default"
              class="gap-1.5 font-semibold cursor-pointer inline-flex items-center"
              @click="showCreateForm = true"
            >
              <Icon name="lucide:plus" class="size-4" aria-hidden="true" />
              <span>Create Your First Campaign</span>
            </Button>
          </div>

          <!-- Workflows Container -->
          <div v-else>
            <!-- Workflows Mobile Cards (Mobile View) -->
            <div class="md:hidden space-y-3">
              <div
                v-for="wf in paginatedWorkflows"
                :key="wf.id"
                class="p-4 bg-card text-card-foreground border border-border rounded-xl shadow-2xs space-y-3 transition-all hover:border-border/80"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <NuxtLink
                      :to="`/workflow/${wf.id}`"
                      class="font-bold text-sm text-foreground hover:text-primary transition-colors block break-words"
                    >
                      {{ wf.name }}
                    </NuxtLink>
                    <p class="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                      <Badge variant="secondary" class="text-[9px] px-1.5 py-0 uppercase">
                        {{ wf.idea_mode }}
                      </Badge>
                      <span v-if="wf.shop_section_name" class="inline-flex items-center gap-1 font-medium text-foreground bg-muted/60 px-1.5 py-0.5 rounded border border-border/50">
                        <Icon name="lucide:folder" class="size-3 text-primary shrink-0" aria-hidden="true" />
                        <span>{{ wf.shop_section_name }}</span>
                      </span>
                      <span>•</span>
                      <span>{{ wf.target_country }}/{{ wf.output_language }}</span>
                      <span>•</span>
                      <time :datetime="wf.created_at">
                        {{ new Date(wf.created_at).toLocaleDateString() }}
                      </time>
                    </p>
                  </div>
                </div>

                <!-- Stage & Progress -->
                <div class="pt-2 border-t border-border/70 space-y-2">
                  <div class="flex items-center justify-between text-xs">
                    <div class="flex items-center gap-1.5">
                      <span
                        class="h-2 w-2 shrink-0 rounded-full"
                        :class="{
                          'bg-amber-500 motion-safe:animate-pulse': isRunning(wf.state),
                          'bg-primary': needsOwner(wf.state),
                          'bg-muted-foreground': wf.state === 'DRAFT' || wf.state === 'CANCELLED',
                          'bg-destructive': wf.state.endsWith('_FAILED'),
                          'bg-emerald-500': !isRunning(wf.state) && !needsOwner(wf.state) && !wf.state.endsWith('_FAILED') && wf.state !== 'DRAFT' && wf.state !== 'CANCELLED'
                        }"
                        aria-hidden="true"
                      />
                      <span class="font-semibold text-foreground">
                        {{ stageLabel(wf.state) }}
                      </span>
                    </div>

                    <span v-if="stageProgress(wf.state)[0] > 0" class="text-[11px] font-mono tabular-nums text-muted-foreground">
                      Step {{ stageProgress(wf.state)[0] }}/{{ stageProgress(wf.state)[1] }}
                    </span>
                  </div>

                  <Progress
                    v-if="stageProgress(wf.state)[0] > 0"
                    :value="stageProgress(wf.state)[0]"
                    :max="stageProgress(wf.state)[1]"
                    class="h-1.5 w-full bg-secondary"
                    indicator-class="bg-primary"
                  />
                </div>

                <!-- Mobile Actions -->
                <div class="pt-2 border-t border-border/70 flex items-center justify-end gap-2">
                  <Button
                    v-if="isRunning(wf.state)"
                    variant="destructive"
                    size="sm"
                    :disabled="pendingWorkflowId === wf.id"
                    class="h-8 px-2.5 text-xs gap-1 cursor-pointer inline-flex items-center"
                    @click="controlWorkflow(wf.id, 'cancel')"
                  >
                    <Icon name="lucide:square" class="size-3 fill-current" aria-hidden="true" />
                    <span>Stop</span>
                  </Button>

                  <Button
                    v-if="isStopped(wf.state)"
                    variant="secondary"
                    size="sm"
                    :disabled="pendingWorkflowId === wf.id"
                    class="h-8 px-2.5 text-xs gap-1 font-medium cursor-pointer inline-flex items-center"
                    @click="controlWorkflow(wf.id, 'rerun')"
                  >
                    <Icon name="lucide:play" class="size-3" aria-hidden="true" />
                    <span>Resume</span>
                  </Button>

                  <NuxtLink :to="`/workflow/${wf.id}`">
                    <Button variant="outline" size="sm" class="h-8 px-3 text-xs gap-1 font-semibold cursor-pointer inline-flex items-center">
                      <span>Open</span>
                      <Icon name="lucide:chevron-right" class="size-3.5" aria-hidden="true" />
                    </Button>
                  </NuxtLink>
                </div>
              </div>
            </div>

            <!-- Workflows Table (Desktop View) -->
            <div class="hidden md:block overflow-x-auto rounded-xl border border-border bg-card">
              <table class="min-w-full text-left text-sm">
                <thead class="border-b border-border bg-secondary/60 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th scope="col" class="px-6 py-3">Campaign</th>
                    <th scope="col" class="px-6 py-3">Shop Section</th>
                    <th scope="col" class="px-6 py-3">Stage & Progress</th>
                    <th scope="col" class="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border bg-card align-middle text-secondary-foreground">
                  <tr
                    v-for="wf in paginatedWorkflows"
                    :key="wf.id"
                    class="transition-colors hover:bg-secondary/40 group"
                  >
                    <td class="px-6 py-4">
                      <NuxtLink
                        :to="`/workflow/${wf.id}`"
                        class="font-bold text-foreground group-hover:text-primary transition-colors focus:outline-none focus:underline"
                      >
                        {{ wf.name }}
                      </NuxtLink>
                      <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <Badge variant="secondary" class="text-[10px] px-2 py-0">
                          {{ wf.idea_mode }}
                        </Badge>
                        <span aria-hidden="true" class="text-border">·</span>
                        <span class="font-medium text-secondary-foreground">{{ wf.target_country }}/{{ wf.output_language }}</span>
                        <span aria-hidden="true" class="text-border">·</span>
                        <time :datetime="wf.created_at" class="text-muted-foreground">
                          {{ new Date(wf.created_at).toLocaleDateString() }}
                        </time>
                      </p>
                    </td>

                    <td class="px-6 py-4">
                      <div v-if="wf.shop_section_name" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-muted/60 text-foreground border border-border/60">
                        <Icon name="lucide:folder" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
                        <span class="truncate max-w-[160px] font-medium">{{ wf.shop_section_name }}</span>
                      </div>
                      <span v-else class="text-xs text-muted-foreground/60 italic">—</span>
                    </td>

                    <td class="px-6 py-4">
                      <div class="space-y-1.5">
                        <div class="flex items-center gap-2">
                          <span
                            class="h-2 w-2 shrink-0 rounded-full"
                            :class="{
                              'bg-amber-500 motion-safe:animate-pulse': isRunning(wf.state),
                              'bg-primary': needsOwner(wf.state),
                              'bg-muted-foreground': wf.state === 'DRAFT' || wf.state === 'CANCELLED',
                              'bg-destructive': wf.state.endsWith('_FAILED'),
                              'bg-emerald-500': !isRunning(wf.state) && !needsOwner(wf.state) && !wf.state.endsWith('_FAILED') && wf.state !== 'DRAFT' && wf.state !== 'CANCELLED'
                            }"
                            aria-hidden="true"
                          />
                          <span class="font-semibold text-xs text-foreground">
                            {{ stageLabel(wf.state) }}
                          </span>
                        </div>

                        <div v-if="stageProgress(wf.state)[0] > 0" class="flex items-center gap-2">
                          <Progress
                            :value="stageProgress(wf.state)[0]"
                            :max="stageProgress(wf.state)[1]"
                            class="h-1.5 w-24 bg-secondary"
                            indicator-class="bg-primary"
                          />
                          <span class="text-[11px] font-medium text-muted-foreground tabular-nums">
                            Step {{ stageProgress(wf.state)[0] }}/{{ stageProgress(wf.state)[1] }}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td class="px-6 py-4">
                      <div class="flex items-center justify-end gap-2">
                        <Button
                          v-if="isRunning(wf.state)"
                          variant="destructive"
                          size="sm"
                          :disabled="pendingWorkflowId === wf.id"
                          :title="`Stop ${wf.name}`"
                          class="h-8 px-2.5 text-xs gap-1 cursor-pointer inline-flex items-center"
                          @click="controlWorkflow(wf.id, 'cancel')"
                        >
                          <Icon name="lucide:square" class="size-3 fill-current" aria-hidden="true" />
                          <span>Stop</span>
                        </Button>

                        <Button
                          v-if="isStopped(wf.state)"
                          variant="secondary"
                          size="sm"
                          :disabled="pendingWorkflowId === wf.id"
                          :title="`Resume ${wf.name}`"
                          class="h-8 px-2.5 text-xs gap-1 font-medium cursor-pointer inline-flex items-center"
                          @click="controlWorkflow(wf.id, 'rerun')"
                        >
                          <Icon name="lucide:play" class="size-3" aria-hidden="true" />
                          <span>Resume</span>
                        </Button>

                        <NuxtLink :to="`/workflow/${wf.id}`">
                          <Button variant="outline" size="sm" class="h-8 px-3 text-xs gap-1 font-semibold cursor-pointer inline-flex items-center">
                            <span>Open</span>
                            <Icon name="lucide:chevron-right" class="size-3.5" aria-hidden="true" />
                          </Button>
                        </NuxtLink>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Pagination Bar -->
            <Pagination
              v-model:current-page="currentPage"
              :total-items="totalFilteredWorkflows"
              :page-size="pageSize"
              class="mt-3"
            />
          </div>
        </CardContent>
      </Card>
    </main>
  </div>
</template>

