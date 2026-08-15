<script setup lang="ts">
/* global $fetch */
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
import {
  Sparkles,
  Plus,
  Compass,
  Lightbulb,
  Layers,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  RotateCw,
  Square,
  ChevronRight,
  Sliders,
} from "lucide-vue-next";
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
import Progress from "~/components/ui/Progress.vue";

const PRODUCT_OPTIONS: SelectOption[] = [
  { value: "mug", label: "Ceramic Mug", icon: "☕" },
  { value: "tshirt", label: "T-Shirt", icon: "👕" },
  { value: "sweatshirt", label: "Sweatshirt / Hoodie", icon: "🧥" },
  { value: "tote_bag", label: "Tote Bag", icon: "👜" },
  { value: "tumbler", label: "Tumbler / Cup", icon: "🥤" },
  { value: "poster", label: "Poster / Wall Art", icon: "🖼️" },
  { value: "sticker", label: "Stickers", icon: "🏷️" },
  { value: "phone_case", label: "Phone Case", icon: "📱" },
  { value: "candle", label: "Scented Candle", icon: "🕯️" },
];

const BUYER_OPTIONS: SelectOption[] = [
  { value: "coffee lovers", label: "Coffee Lovers & Baristas", icon: "☕" },
  { value: "teachers", label: "Teachers & Educators", icon: "👩‍🏫" },
  { value: "dog lovers", label: "Dog Moms & Pet Parents", icon: "🐾" },
  { value: "plant lovers", label: "Plant Enthusiasts & Botanists", icon: "🌿" },
  { value: "book lovers", label: "Bookworms & Readers", icon: "📚" },
  { value: "campers & hikers", label: "Outdoor Campers & Hikers", icon: "🏕️" },
  { value: "nurses", label: "Nurses & Healthcare", icon: "🏥" },
  { value: "moms", label: "Mothers & New Moms", icon: "👩‍👧" },
  { value: "dads", label: "Fathers & Dads", icon: "👨‍👦" },
  { value: "gamers", label: "Gamers & Techies", icon: "🎮" },
  { value: "crafters", label: "Crafters & DIYers", icon: "🎨" },
  { value: "minimalists", label: "Minimalists & Modernists", icon: "✨" },
];

const NICHE_OPTIONS: SelectOption[] = [
  { value: "retro camping", label: "Retro Camping & Wilderness", icon: "🏕️" },
  { value: "black cats", label: "Black Cats & Witchy", icon: "🐈‍⬛" },
  { value: "cottagecore", label: "Cottagecore & Mushrooms", icon: "🍄" },
  { value: "vintage floral", label: "Vintage Botanical & Floral", icon: "🌸" },
  { value: "cozy coffee", label: "Cozy Coffee & Books", icon: "☕" },
  { value: "space celestial", label: "Space & Celestial Stars", icon: "🚀" },
  { value: "punny food", label: "Punny Food & Cooking", icon: "🥑" },
  { value: "golden retriever", label: "Golden Retrievers & Dogs", icon: "🐶" },
  { value: "desert cacti", label: "Desert & Southwest Cacti", icon: "🌵" },
  { value: "coastal ocean", label: "Coastal & Ocean Waves", icon: "🌊" },
];

const STYLE_OPTIONS: SelectOption[] = [
  { value: "watercolor", label: "Soft Watercolor & Wash", icon: "🎨" },
  { value: "minimalist line art", label: "Minimalist Line Art & Monoline", icon: "✏️" },
  { value: "vintage retro 70s", label: "Vintage 70s / Retro Distressed", icon: "📻" },
  { value: "boho botanical", label: "Boho Botanical & Earthy", icon: "🌿" },
  { value: "kawaii cute", label: "Cute Kawaii & Pastel", icon: "🌈" },
  { value: "bold typography", label: "Bold Typography & Lettering", icon: "📜" },
  { value: "engraving woodcut", label: "Engraving & Woodcut Vintage", icon: "✒️" },
  { value: "pixel art", label: "8-Bit / 16-Bit Pixel Art", icon: "👾" },
  { value: "geometric vector", label: "Geometric Clean Vector", icon: "📐" },
  { value: "oil painting", label: "Classic Oil Painting Impressionist", icon: "🖌️" },
];

const OCCASION_OPTIONS: SelectOption[] = [
  { value: "birthday", label: "Birthday", icon: "🎂" },
  { value: "christmas", label: "Christmas & Holiday", icon: "🎄" },
  { value: "halloween", label: "Halloween & Fall", icon: "🎃" },
  { value: "valentines", label: "Valentine's Day", icon: "💝" },
  { value: "mothers day", label: "Mother's Day", icon: "👩" },
  { value: "fathers day", label: "Father's Day", icon: "👨" },
  { value: "graduation", label: "Graduation", icon: "🎓" },
  { value: "wedding", label: "Wedding & Anniversary", icon: "💍" },
  { value: "thanksgiving", label: "Thanksgiving", icon: "🦃" },
  { value: "baby shower", label: "Baby Shower & Newborn", icon: "👶" },
  { value: "summer vacation", label: "Summer Vacation & Travel", icon: "🌴" },
  { value: "everyday", label: "Everyday / No Special Occasion", icon: "✨" },
];

const SEASON_OPTIONS: SelectOption[] = [
  { value: "winter", label: "Winter", icon: "❄️" },
  { value: "spring", label: "Spring", icon: "🌸" },
  { value: "summer", label: "Summer", icon: "☀️" },
  { value: "autumn", label: "Autumn / Fall", icon: "🍂" },
  { value: "evergreen", label: "Year-Round / Evergreen", icon: "🌲" },
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
const targetBuyer = ref("");
const intendedProductUses = ref<string[]>(["mug"]);
const isCreating = ref(false);
const creationError = ref<string | null>(null);

// Original Idea fields (for user-idea/hybrid modes)
const originalText = ref("");
const slogan = ref("");
const desiredStyle = ref("");
const audience = ref("");
const occasion = ref("");
const season = ref("");
const preferredNiche = ref("");

// Filter state
const searchQuery = ref("");
const selectedFilter = ref<"all" | "active" | "needs-review" | "completed">("all");

// Clear inapplicable fields when mode changes to prevent stale data submission
watch(ideaMode, (newMode) => {
  if (newMode === "market-led") {
    originalText.value = "";
    slogan.value = "";
    desiredStyle.value = "";
    audience.value = "";
    occasion.value = "";
    season.value = "";
  } else {
    preferredNiche.value = "";
  }
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
      if (preferredNiche.value.trim()) {
        resolvedName = `${targetCountry.value.toUpperCase()} Trend Discovery (${preferredNiche.value.trim()}) - ${monthYear}`;
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
      target_buyer: targetBuyer.value.trim() || null,
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
        desired_style: desiredStyle.value.trim() || null,
        audience: audience.value.trim() || null,
        occasion: occasion.value.trim() || null,
        season: season.value.trim() || null,
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
    targetBuyer.value = "";
    intendedProductUses.value = ["mug"];
    originalText.value = "";
    slogan.value = "";
    desiredStyle.value = "";
    audience.value = "";
    occasion.value = "";
    season.value = "";
    preferredNiche.value = "";

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

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter(
      (wf) =>
        wf.name.toLowerCase().includes(q) ||
        wf.idea_mode.toLowerCase().includes(q) ||
        wf.target_country.toLowerCase().includes(q)
    );
  }
  return list;
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
  await loadWorkflows();
  if (hasActiveWorkflows.value) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="min-h-screen bg-zinc-50/80 pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Dashboard Hero Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-zinc-200/80 pb-8">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600">
            <Sparkles class="h-4 w-4" />
            <span>Digital Product Automation</span>
          </div>
          <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-900">
            Etsy PNG Automation
          </h1>
          <p class="text-sm text-zinc-500 max-w-2xl">
            Autonomous research-to-draft engine for high-resolution digital PNG art. Human approval gates at every milestone.
          </p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            v-if="!showCreateForm"
            variant="default"
            size="lg"
            class="shadow-md shadow-indigo-600/20 gap-2 font-semibold"
            @click="showCreateForm = true"
          >
            <Plus class="h-4 w-4" />
            <span>Create New Campaign</span>
          </Button>
          <Button
            v-else
            variant="outline"
            size="lg"
            class="font-semibold"
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
            <span class="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Total Campaigns</span>
            <Layers class="h-4 w-4 text-zinc-400" />
          </div>
          <p class="text-2xl font-bold text-zinc-900 mt-2">{{ totalCount }}</p>
          <span class="text-[11px] text-zinc-400">All registered workflows</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-amber-700 uppercase tracking-wide">In Progress</span>
            <RotateCw
              class="h-4 w-4"
              :class="runningCount > 0 ? 'text-amber-600 animate-spin' : 'text-amber-600/50'"
            />
          </div>
          <p class="text-2xl font-bold text-amber-900 mt-2">{{ runningCount }}</p>
          <span class="text-[11px] text-amber-700/80">Active background tasks</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-indigo-700 uppercase tracking-wide">Needs Gate Review</span>
            <Clock class="h-4 w-4 text-indigo-600" />
          </div>
          <p class="text-2xl font-bold text-indigo-900 mt-2">{{ attentionCount }}</p>
          <span class="text-[11px] text-indigo-700/80">Awaiting human sign-off</span>
        </Card>

        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-emerald-700 uppercase tracking-wide">Approved / Complete</span>
            <CheckCircle2 class="h-4 w-4 text-emerald-600" />
          </div>
          <p class="text-2xl font-bold text-emerald-900 mt-2">{{ completedCount }}</p>
          <span class="text-[11px] text-emerald-700/80">Ready for listing</span>
        </Card>
      </div>

      <!-- Campaign Creation Card -->
      <Card v-if="showCreateForm" class="shadow-lg border-indigo-200 bg-gradient-to-b from-white to-indigo-50/20">
        <CardHeader class="pb-4">
          <div class="flex items-center gap-2.5">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
              <Sparkles class="h-5 w-5" />
            </div>
            <div>
              <CardTitle class="text-xl">Start a New Design Campaign</CardTitle>
              <CardDescription>Configure market targeting, choose an input mode, and kick off AI synthesis</CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <Alert v-if="creationError" variant="destructive" class="mb-6">
            <AlertCircle class="h-4 w-4" />
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
                      ? 'border-indigo-600 bg-indigo-50/50 shadow-2xs'
                      : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/50',
                  ]"
                  @click="ideaMode = 'market-led'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Compass class="h-4 w-4 text-indigo-600" />
                      <span class="font-bold text-sm text-zinc-900">Discover Ideas</span>
                    </div>
                    <Badge v-if="ideaMode === 'market-led'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-indigo-700 mb-1">Market-Led Discovery</p>
                  <p class="text-xs text-zinc-500 leading-relaxed">
                    AI searches seasonal Etsy trends and generates 3 validated design concepts automatically.
                  </p>
                </div>

                <!-- Mode 2: User Idea -->
                <div
                  :class="[
                    'relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-150',
                    ideaMode === 'user-idea'
                      ? 'border-indigo-600 bg-indigo-50/50 shadow-2xs'
                      : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/50',
                  ]"
                  @click="ideaMode = 'user-idea'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Lightbulb class="h-4 w-4 text-indigo-600" />
                      <span class="font-bold text-sm text-zinc-900">Use My Idea</span>
                    </div>
                    <Badge v-if="ideaMode === 'user-idea'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-indigo-700 mb-1">Idea Optimization</p>
                  <p class="text-xs text-zinc-500 leading-relaxed">
                    Provide your own theme or slogan. The engine refines keywords, prompts, and target appeal.
                  </p>
                </div>

                <!-- Mode 3: Hybrid -->
                <div
                  :class="[
                    'relative rounded-xl border-2 p-4 cursor-pointer transition-all duration-150',
                    ideaMode === 'hybrid'
                      ? 'border-indigo-600 bg-indigo-50/50 shadow-2xs'
                      : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50/50',
                  ]"
                  @click="ideaMode = 'hybrid'"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Sliders class="h-4 w-4 text-indigo-600" />
                      <span class="font-bold text-sm text-zinc-900">Hybrid Approach</span>
                    </div>
                    <Badge v-if="ideaMode === 'hybrid'" variant="default" class="h-5 px-1.5 text-[10px]">
                      Selected
                    </Badge>
                  </div>
                  <p class="text-xs font-semibold text-indigo-700 mb-1">Direction + Signals</p>
                  <p class="text-xs text-zinc-500 leading-relaxed">
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
                <span v-if="ideaMode === 'market-led'" class="text-[11px] text-zinc-400">
                  Optional — auto-generates if left blank
                </span>
              </div>

              <div class="space-y-1.5">
                <Label for="target-country">Target Marketplace Country</Label>
                <select
                  id="target-country"
                  v-model="targetCountry"
                  class="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
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
                  placeholder="Select or type buyer..."
                />
              </div>

              <div v-if="ideaMode === 'market-led'" class="space-y-1.5">
                <Label for="preferred-niche">Preferred Niche (Optional)</Label>
                <CustomizableSelect
                  id="preferred-niche"
                  v-model="preferredNiche"
                  :options="NICHE_OPTIONS"
                  storage-key="etsy_custom_niches"
                  placeholder="Select or type niche..."
                />
              </div>

              <div :class="ideaMode !== 'market-led' ? 'md:col-span-1 lg:col-span-2' : ''" class="space-y-1.5">
                <Label for="product-uses">Intended Physical Products</Label>
                <CustomizableSelect
                  id="product-uses"
                  v-model="intendedProductUses"
                  :options="PRODUCT_OPTIONS"
                  storage-key="etsy_custom_products"
                  :is-multi="true"
                  placeholder="Select products..."
                />
              </div>
            </div>

            <!-- Step 3: Wording / Brief inputs (for user-idea/hybrid modes) -->
            <div v-if="ideaMode !== 'market-led'" class="border-t border-zinc-200/80 pt-6 space-y-4">
              <h3 class="text-base font-bold text-zinc-900">
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
                    placeholder="Select or type style..."
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
                    placeholder="Select or type audience..."
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="occasion">Occasion (Optional)</Label>
                  <CustomizableSelect
                    id="occasion"
                    v-model="occasion"
                    :options="OCCASION_OPTIONS"
                    storage-key="etsy_custom_occasions"
                    placeholder="Select or type occasion..."
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="season">Season (Optional)</Label>
                  <CustomizableSelect
                    id="season"
                    v-model="season"
                    :options="SEASON_OPTIONS"
                    storage-key="etsy_custom_seasons"
                    placeholder="Select or type season..."
                  />
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between border-t border-zinc-100 pt-4">
              <div class="flex items-center gap-2 text-xs text-zinc-500">
                <Clock class="h-4 w-4 text-indigo-600" />
                <span>Runs in background · Pauses at Gate 1 for review</span>
              </div>

              <Button
                type="submit"
                variant="default"
                size="lg"
                :loading="isCreating"
                class="shadow-md shadow-indigo-600/20 font-bold"
              >
                <span>
                  {{
                    ideaMode === 'market-led' ? 'Discover 3 Ideas' :
                    ideaMode === 'user-idea' ? 'Research My Idea' :
                    'Generate Variations'
                  }}
                </span>
                <ArrowRight v-if="!isCreating" class="h-4 w-4 ml-1" />
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
              <CardDescription>Track pipeline execution, monitor approval gates, and manage drafts</CardDescription>
            </div>

            <!-- Search & Filters -->
            <div class="flex items-center gap-2">
              <div class="relative w-48 sm:w-60">
                <Input
                  v-model="searchQuery"
                  placeholder="Search campaigns..."
                  class="pl-8 text-xs h-8"
                />
                <Search class="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-400 pointer-events-none" />
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent class="pt-0">
          <Alert v-if="controlError" variant="destructive" class="mb-4">
            <AlertCircle class="h-4 w-4" />
            <AlertDescription>{{ controlError }}</AlertDescription>
          </Alert>

          <div v-if="isListLoading" class="flex flex-col items-center justify-center py-16 text-zinc-400 gap-2">
            <RotateCw class="h-6 w-6 animate-spin text-indigo-600" />
            <p class="text-sm font-medium">Loading campaigns...</p>
          </div>

          <Alert v-else-if="listError" variant="warning" class="mb-4">
            <AlertCircle class="h-4 w-4" />
            <AlertDescription>{{ listError }}</AlertDescription>
          </Alert>

          <!-- Empty State -->
          <div v-else-if="filteredWorkflows.length === 0" class="text-center py-16 px-4">
            <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 mb-4 border border-indigo-100 shadow-2xs">
              <Sparkles class="h-7 w-7" />
            </div>
            <h3 class="text-base font-bold text-zinc-900 mb-1">
              {{ searchQuery ? 'No matching campaigns' : 'No active campaigns' }}
            </h3>
            <p class="text-zinc-500 text-xs mb-6 max-w-sm mx-auto">
              {{ searchQuery ? 'Try adjusting your search query or clear filters.' : 'Get started by creating your first product design workflow with automated research.' }}
            </p>
            <Button
              v-if="!searchQuery"
              variant="default"
              size="default"
              class="gap-1.5 font-semibold"
              @click="showCreateForm = true"
            >
              <Plus class="h-4 w-4" />
              <span>Create Your First Campaign</span>
            </Button>
          </div>

          <!-- Workflows Table -->
          <div v-else class="overflow-x-auto rounded-xl border border-zinc-200/80">
            <table class="min-w-full text-left text-sm">
              <thead class="border-b border-zinc-200 bg-zinc-50/80 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                <tr>
                  <th scope="col" class="px-6 py-3">Campaign</th>
                  <th scope="col" class="px-6 py-3">Stage & Progress</th>
                  <th scope="col" class="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-zinc-100 bg-white align-middle text-zinc-600">
                <tr
                  v-for="wf in filteredWorkflows"
                  :key="wf.id"
                  class="transition-colors hover:bg-zinc-50/80 group"
                >
                  <td class="px-6 py-4">
                    <NuxtLink
                      :to="`/workflow/${wf.id}`"
                      class="font-bold text-zinc-900 group-hover:text-indigo-600 transition-colors focus:outline-none focus:underline"
                    >
                      {{ wf.name }}
                    </NuxtLink>
                    <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500">
                      <Badge variant="secondary" class="text-[10px] px-2 py-0">
                        {{ wf.idea_mode }}
                      </Badge>
                      <span aria-hidden="true" class="text-zinc-300">·</span>
                      <span class="font-medium text-zinc-600">{{ wf.target_country }}/{{ wf.output_language }}</span>
                      <span aria-hidden="true" class="text-zinc-300">·</span>
                      <time :datetime="wf.created_at" class="text-zinc-400">
                        {{ new Date(wf.created_at).toLocaleDateString() }}
                      </time>
                    </p>
                  </td>

                  <td class="px-6 py-4">
                    <div class="space-y-1.5">
                      <div class="flex items-center gap-2">
                        <span
                          class="h-2 w-2 shrink-0 rounded-full"
                          :class="{
                            'bg-amber-500 motion-safe:animate-pulse': isRunning(wf.state),
                            'bg-indigo-500': needsOwner(wf.state),
                            'bg-zinc-400': wf.state === 'DRAFT' || wf.state === 'CANCELLED',
                            'bg-rose-500': wf.state.endsWith('_FAILED'),
                            'bg-emerald-500': !isRunning(wf.state) && !needsOwner(wf.state) && !wf.state.endsWith('_FAILED') && wf.state !== 'DRAFT' && wf.state !== 'CANCELLED'
                          }"
                          aria-hidden="true"
                        />
                        <span class="font-semibold text-xs text-zinc-800">
                          {{ stageLabel(wf.state) }}
                        </span>
                      </div>

                      <div v-if="stageProgress(wf.state)[0] > 0" class="flex items-center gap-2">
                        <Progress
                          :value="stageProgress(wf.state)[0]"
                          :max="stageProgress(wf.state)[1]"
                          class="h-1.5 w-24 bg-zinc-100"
                          indicator-class="bg-indigo-600"
                        />
                        <span class="text-[11px] font-medium text-zinc-400 tabular-nums">
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
                        class="h-8 px-2.5 text-xs gap-1"
                        @click="controlWorkflow(wf.id, 'cancel')"
                      >
                        <Square class="h-3 w-3 fill-current" />
                        <span>Stop</span>
                      </Button>

                      <Button
                        v-if="isStopped(wf.state)"
                        variant="secondary"
                        size="sm"
                        :disabled="pendingWorkflowId === wf.id"
                        :title="`Resume ${wf.name}`"
                        class="h-8 px-2.5 text-xs gap-1 font-medium"
                        @click="controlWorkflow(wf.id, 'rerun')"
                      >
                        <RotateCw class="h-3 w-3" />
                        <span>Resume</span>
                      </Button>

                      <NuxtLink :to="`/workflow/${wf.id}`">
                        <Button variant="outline" size="sm" class="h-8 px-3 text-xs gap-1 font-semibold">
                          <span>Open</span>
                          <ChevronRight class="h-3.5 w-3.5" />
                        </Button>
                      </NuxtLink>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </main>
  </div>
</template>
