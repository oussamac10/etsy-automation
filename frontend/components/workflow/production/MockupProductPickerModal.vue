<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue";
import type { MockupAsset } from "~/types/mockup";
import {
  SUPPORTED_PRODUCT_TYPES,
  getProductLabel,
  getProductIconName,
  normalizeProductKey,
} from "~/utils/mockupProducts";
import Button from "~/components/ui/Button.vue";
import { useLibraryProducts } from "~/composables/useLibraryProducts";

const props = defineProps<{
  open: boolean;
  workflowId?: string;
  existingCategories?: string[];
  campaignProducts?: string[];
  savedSuggestions?: string[];
  mockupsByProduct?: Record<string, MockupAsset[]>;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "select", productKey: string): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase || "http://localhost:8800";
const { libraryProductOptions, fetchLibraryProducts } = useLibraryProducts();

onMounted(() => {
  fetchLibraryProducts();
  if (props.savedSuggestions && props.savedSuggestions.length > 0) {
    initFromSavedSuggestions(props.savedSuggestions);
  }
});

const activeTab = ref<"recommended" | "ai" | "custom" | "all">("recommended");
const searchQuery = ref("");
const isGeneratingIdeas = ref(false);
const generateError = ref<string | null>(null);
const aiGeneratedItems = ref<Array<{ key: string; label: string; icon: string }>>([]);

// Reactive mockup count directly calculated from props.mockupsByProduct
function getMockupCount(key: string): number {
  if (!props.mockupsByProduct) return 0;
  const normalized = normalizeProductKey(key);
  return (props.mockupsByProduct[normalized] || []).length;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : null;
}

// 1. Campaign Target Products
const campaignItems = computed(() => {
  const seen = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string }> = [];

  for (const c of props.campaignProducts || []) {
    const k = normalizeProductKey(c);
    if (k && !seen.has(k)) {
      seen.add(k);
      items.push({
        key: k,
        label: getProductLabel(k),
        icon: getProductIconName(k),
      });
    }
  }
  return items;
});

// 2. Custom categories from library
const customItems = computed(() => {
  const standardKeys = new Set(SUPPORTED_PRODUCT_TYPES.map((p) => p.key));
  const chosenKeys = new Set([
    ...campaignItems.value.map((i) => i.key),
    ...aiGeneratedItems.value.map((i) => i.key),
  ]);
  const set = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string }> = [];

  for (const opt of libraryProductOptions.value) {
    if (opt.isCustom && !standardKeys.has(opt.value)) {
      const k = normalizeProductKey(opt.value);
      if (k && !set.has(k) && !chosenKeys.has(k)) {
        set.add(k);
        items.push({
          key: k,
          label: getProductLabel(k),
          icon: getProductIconName(k),
        });
      }
    }
  }
  return items;
});

// 3. All Standard Catalog Categories
const allCatalogItems = computed(() => {
  return SUPPORTED_PRODUCT_TYPES.map((p) => ({
    key: p.key,
    label: p.label,
    icon: p.icon,
  }));
});

// Combined search results when searching
const searchFilteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return [];
  const map = new Map<string, { key: string; label: string; icon: string }>();

  for (const item of [...campaignItems.value, ...aiGeneratedItems.value, ...customItems.value, ...allCatalogItems.value]) {
    if (item.label.toLowerCase().includes(q) || item.key.toLowerCase().includes(q)) {
      if (!map.has(item.key)) {
        map.set(item.key, item);
      }
    }
  }
  return Array.from(map.values());
});

// Initialize AI recommendations from saved suggestions
function initFromSavedSuggestions(suggestions?: string[]) {
  if (!suggestions || suggestions.length === 0) return;
  const campaignKeys = new Set(campaignItems.value.map((i) => i.key));
  const seen = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string }> = [];

  for (const s of suggestions) {
    const clean = String(s).trim().replace(/^['"[\]\s]+|['"[\]\s]+$/g, "");
    const k = normalizeProductKey(clean);
    if (k && !campaignKeys.has(k) && !seen.has(k)) {
      seen.add(k);
      items.push({
        key: k,
        label: getProductLabel(clean),
        icon: getProductIconName(k),
      });
    }
  }
  if (items.length > 0) {
    aiGeneratedItems.value = items;
  }
}

watch(
  () => props.savedSuggestions,
  (newVal) => {
    if (newVal && newVal.length > 0) {
      initFromSavedSuggestions(newVal);
    }
  },
  { immediate: true, deep: true }
);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      searchQuery.value = "";
      if (props.savedSuggestions && props.savedSuggestions.length > 0 && aiGeneratedItems.value.length === 0) {
        initFromSavedSuggestions(props.savedSuggestions);
      }
    }
  }
);

// DB persistence sync
async function syncSuggestionsToDb(suggestions: string[]) {
  if (!props.workflowId) return;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;

    await $fetch(`${apiBase}/api/v1/workflows/${props.workflowId}/mockups/suggested-products`, {
      method: "PUT",
      headers,
      body: { suggestions },
      credentials: "include",
    });
  } catch (err) {
    console.error("Failed to sync mockup suggestions to DB:", err);
  }
}

async function handleGenerateAiIdeas() {
  if (!props.workflowId || isGeneratingIdeas.value) return;
  isGeneratingIdeas.value = true;
  generateError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;

    const res = await $fetch<{ suggestions: string[] }>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/mockups/suggest-ideas`,
      {
        method: "POST",
        headers,
        credentials: "include",
      }
    );

    if (res && Array.isArray(res.suggestions)) {
      const campaignKeys = new Set(campaignItems.value.map((i) => i.key));
      const seen = new Set<string>();
      const items: Array<{ key: string; label: string; icon: string }> = [];

      for (const s of res.suggestions) {
        const clean = String(s).trim().replace(/^['"[\]\s]+|['"[\]\s]+$/g, "");
        const k = normalizeProductKey(clean);
        if (k && !campaignKeys.has(k) && !seen.has(k)) {
          seen.add(k);
          items.push({
            key: k,
            label: getProductLabel(clean),
            icon: getProductIconName(k),
          });
        }
      }
      aiGeneratedItems.value = items;
    }
  } catch (err: unknown) {
    generateError.value = err instanceof Error ? err.message : "Failed to generate mockup ideas.";
  } finally {
    isGeneratingIdeas.value = false;
  }
}

async function removeAiIdea(key: string) {
  aiGeneratedItems.value = aiGeneratedItems.value.filter((item) => item.key !== key);
  const remainingLabels = aiGeneratedItems.value.map((i) => i.label);
  await syncSuggestionsToDb(remainingLabels);
}

async function clearAllAiIdeas() {
  aiGeneratedItems.value = [];
  await syncSuggestionsToDb([]);
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
    <div class="bg-card text-card-foreground rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden border border-border animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[84vh]">
      <!-- 1. Modal Header -->
      <div class="px-5 py-3.5 border-b border-border flex items-center justify-between bg-secondary/30 shrink-0">
        <div class="flex items-center gap-2">
          <div class="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
            <Icon name="lucide:layout-grid" class="size-4" aria-hidden="true" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-foreground">Select Product Type</h3>
            <p class="text-[11px] text-muted-foreground">Pick a product category to add or composite mockups</p>
          </div>
        </div>
        <button
          type="button"
          class="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- 2. Search & Filter Bar -->
      <div class="px-5 pt-3 pb-2.5 border-b border-border bg-slate-50/50 space-y-2.5 shrink-0">
        <!-- Search Input -->
        <div class="relative">
          <Icon name="lucide:search" class="size-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search product categories (e.g. Mug, Shirt, Blanket, Candle)..."
            class="w-full h-8 pl-8 pr-7 rounded-lg border border-border bg-card text-xs text-foreground placeholder:text-muted-foreground/70 focus:outline-hidden focus:ring-1 focus:ring-primary focus:border-primary transition-all"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
            @click="searchQuery = ''"
          >
            <Icon name="lucide:x" class="size-3" aria-hidden="true" />
          </button>
        </div>

        <!-- Filter Tabs (Hidden during active search for simplicity) -->
        <div v-if="!searchQuery" class="flex items-center gap-1 overflow-x-auto pb-0.5 no-scrollbar text-xs">
          <button
            type="button"
            class="px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap"
            :class="activeTab === 'recommended' ? 'bg-primary text-white shadow-2xs' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'"
            @click="activeTab = 'recommended'"
          >
            <Icon name="lucide:sparkles" class="size-3" aria-hidden="true" />
            <span>Recommended</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full"
              :class="activeTab === 'recommended' ? 'bg-white/20 text-white' : 'bg-secondary text-muted-foreground'"
            >
              {{ campaignItems.length + aiGeneratedItems.length }}
            </span>
          </button>

          <button
            type="button"
            class="px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap"
            :class="activeTab === 'ai' ? 'bg-amber-500 text-white shadow-2xs' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'"
            @click="activeTab = 'ai'"
          >
            <Icon name="lucide:wand-2" class="size-3" aria-hidden="true" />
            <span>AI Ideas</span>
            <span
              v-if="aiGeneratedItems.length > 0"
              class="text-[10px] px-1.5 py-0.2 rounded-full"
              :class="activeTab === 'ai' ? 'bg-white/20 text-white' : 'bg-amber-500/20 text-amber-600 dark:text-amber-400'"
            >
              {{ aiGeneratedItems.length }}
            </span>
          </button>

          <button
            v-if="customItems.length > 0"
            type="button"
            class="px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap"
            :class="activeTab === 'custom' ? 'bg-secondary-foreground text-white shadow-2xs' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'"
            @click="activeTab = 'custom'"
          >
            <Icon name="lucide:folder" class="size-3" aria-hidden="true" />
            <span>Custom Library</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-secondary text-muted-foreground">
              {{ customItems.length }}
            </span>
          </button>

          <button
            type="button"
            class="px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap"
            :class="activeTab === 'all' ? 'bg-secondary-foreground text-white shadow-2xs' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'"
            @click="activeTab = 'all'"
          >
            <Icon name="lucide:package" class="size-3" aria-hidden="true" />
            <span>All Catalog</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full bg-secondary text-muted-foreground">
              {{ allCatalogItems.length }}
            </span>
          </button>
        </div>
      </div>

      <!-- 3. Modal Body Grid Area -->
      <div class="p-5 overflow-y-auto flex-1 space-y-4">
        <!-- Search Active View -->
        <div v-if="searchQuery" class="space-y-3">
          <div class="flex items-center justify-between text-xs text-muted-foreground">
            <span>Found <b>{{ searchFilteredItems.length }}</b> matching {{ searchFilteredItems.length === 1 ? 'category' : 'categories' }}</span>
          </div>

          <div v-if="searchFilteredItems.length > 0" class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in searchFilteredItems"
              :key="item.key"
              type="button"
              class="relative p-2.5 rounded-xl border border-border hover:border-primary hover:bg-primary/5 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[6.25rem]"
              @click="emit('select', item.key)"
            >
              <div class="h-8 w-8 rounded-lg bg-secondary/80 group-hover:bg-primary/10 flex items-center justify-center text-secondary-foreground group-hover:text-primary transition-colors shrink-0">
                <Icon :name="item.icon" class="size-4" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="item.label">
                {{ item.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="getMockupCount(item.key) > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-secondary text-muted-foreground border border-border'"
              >
                {{ getMockupCount(item.key) }} {{ getMockupCount(item.key) === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>

          <div v-else class="py-8 text-center text-xs text-muted-foreground">
            No product categories match "<b>{{ searchQuery }}</b>".
          </div>
        </div>

        <!-- TAB 1: Recommended (Target Campaign Products + Saved AI Ideas) -->
        <div v-else-if="activeTab === 'recommended'" class="space-y-4">
          <!-- Campaign Target Section -->
          <div v-if="campaignItems.length > 0" class="space-y-2">
            <div class="flex items-center gap-1.5">
              <Icon name="lucide:check-circle-2" class="size-3.5 text-primary" aria-hidden="true" />
              <label class="text-[11px] font-bold text-foreground uppercase tracking-wider">
                Campaign Target Products
              </label>
            </div>
            <div class="grid grid-cols-3 gap-2.5">
              <button
                v-for="item in campaignItems"
                :key="item.key"
                type="button"
                class="relative p-2.5 rounded-xl border border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[6.25rem]"
                @click="emit('select', item.key)"
              >
                <div class="h-8 w-8 rounded-lg bg-primary/10 group-hover:bg-primary flex items-center justify-center text-primary group-hover:text-white transition-colors shrink-0">
                  <Icon :name="item.icon" class="size-4" aria-hidden="true" />
                </div>
                <span class="text-xs font-bold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="item.label">
                  {{ item.label }}
                </span>
                <span
                  class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                  :class="getMockupCount(item.key) > 0 ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30' : 'bg-card text-muted-foreground border border-border'"
                >
                  {{ getMockupCount(item.key) }} {{ getMockupCount(item.key) === 1 ? 'mockup' : 'mockups' }}
                </span>
              </button>
            </div>
          </div>

          <!-- AI Generated Ideas Section -->
          <div class="space-y-2 pt-1 border-t border-border">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <Icon name="lucide:sparkles" class="size-3.5 text-amber-500" aria-hidden="true" />
                <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                  AI Product Recommendations
                </label>
              </div>
              <div class="flex items-center gap-1.5">
                <Button
                  v-if="aiGeneratedItems.length > 0"
                  variant="ghost"
                  size="sm"
                  class="h-6 text-[11px] text-muted-foreground hover:text-red-600 px-1.5 cursor-pointer"
                  title="Clear ideas"
                  @click="clearAllAiIdeas"
                >
                  <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                  <span>Clear</span>
                </Button>
                <Button
                  v-if="workflowId"
                  variant="outline"
                  size="sm"
                  class="h-6.5 text-[11px] font-bold border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-foreground gap-1 cursor-pointer px-2 shadow-2xs"
                  :disabled="isGeneratingIdeas"
                  @click="handleGenerateAiIdeas"
                >
                  <Icon
                    :name="isGeneratingIdeas ? 'lucide:loader-2' : 'lucide:sparkles'"
                    class="size-3 text-amber-500"
                    :class="{ 'animate-spin': isGeneratingIdeas }"
                    aria-hidden="true"
                  />
                  <span>{{ isGeneratingIdeas ? 'Generating...' : aiGeneratedItems.length > 0 ? 'Regenerate' : 'Generate Mockup Ideas' }}</span>
                </Button>
              </div>
            </div>

            <!-- Error Banner -->
            <div v-if="generateError" class="p-2 rounded-lg bg-destructive/10 border border-destructive/30 text-xs text-destructive">
              {{ generateError }}
            </div>

            <!-- AI Cards Grid -->
            <div v-if="aiGeneratedItems.length > 0" class="grid grid-cols-3 gap-2.5">
              <div
                v-for="item in aiGeneratedItems"
                :key="item.key"
                class="relative group"
              >
                <button
                  type="button"
                  class="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-card border border-border text-muted-foreground hover:text-destructive hover:border-destructive/30 hover:bg-destructive/10 flex items-center justify-center shadow-xs transition-colors z-10 cursor-pointer"
                  title="Remove this recommendation"
                  @click.stop="removeAiIdea(item.key)"
                >
                  <Icon name="lucide:x" class="size-3" aria-hidden="true" />
                </button>

                <button
                  type="button"
                  class="w-full h-full p-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 hover:border-amber-500/50 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer text-center min-h-[6.25rem]"
                  @click="emit('select', item.key)"
                >
                  <div class="h-8 w-8 rounded-lg bg-amber-500/20 group-hover:bg-amber-500 flex items-center justify-center text-amber-500 group-hover:text-white transition-colors shrink-0">
                    <Icon :name="item.icon" class="size-4" aria-hidden="true" />
                  </div>
                  <span class="text-xs font-bold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="item.label">
                    {{ item.label }}
                  </span>
                  <span
                    class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                    :class="getMockupCount(item.key) > 0 ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30' : 'bg-card text-muted-foreground border border-border'"
                  >
                    {{ getMockupCount(item.key) }} {{ getMockupCount(item.key) === 1 ? 'mockup' : 'mockups' }}
                  </span>
                </button>
              </div>
            </div>

            <div v-else-if="!isGeneratingIdeas" class="p-3 rounded-xl border border-dashed border-border bg-slate-50/50 text-center">
              <p class="text-xs text-muted-foreground">
                Click <b>Generate Mockup Ideas</b> to let AI suggest top-selling products tailored for this design.
              </p>
            </div>
          </div>
        </div>

        <!-- TAB 2: AI Ideas Dedicated View -->
        <div v-else-if="activeTab === 'ai'" class="space-y-3">
          <div class="flex items-center justify-between">
            <p class="text-xs text-muted-foreground">
              AI curated products based on your slogan and niche:
            </p>
            <div class="flex items-center gap-1.5">
              <Button
                v-if="aiGeneratedItems.length > 0"
                variant="ghost"
                size="sm"
                class="h-6.5 text-xs text-muted-foreground hover:text-red-600 px-2 cursor-pointer"
                @click="clearAllAiIdeas"
              >
                <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                <span>Clear All</span>
              </Button>
              <Button
                v-if="workflowId"
                variant="default"
                size="sm"
                class="h-6.5 text-xs font-bold gap-1 cursor-pointer px-2.5 shadow-2xs"
                :disabled="isGeneratingIdeas"
                @click="handleGenerateAiIdeas"
              >
                <Icon
                  :name="isGeneratingIdeas ? 'lucide:loader-2' : 'lucide:sparkles'"
                  class="size-3"
                  :class="{ 'animate-spin': isGeneratingIdeas }"
                  aria-hidden="true"
                />
                <span>{{ isGeneratingIdeas ? 'Generating Ideas...' : aiGeneratedItems.length > 0 ? 'Regenerate Ideas' : 'Generate Ideas' }}</span>
              </Button>
            </div>
          </div>

          <div v-if="aiGeneratedItems.length > 0" class="grid grid-cols-3 gap-2.5">
            <div
              v-for="item in aiGeneratedItems"
              :key="item.key"
              class="relative group"
            >
              <button
                type="button"
                class="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-card border border-border text-muted-foreground hover:text-destructive hover:border-destructive/30 hover:bg-destructive/10 flex items-center justify-center shadow-xs transition-colors z-10 cursor-pointer"
                title="Remove this idea"
                @click.stop="removeAiIdea(item.key)"
              >
                <Icon name="lucide:x" class="size-3" aria-hidden="true" />
              </button>

              <button
                type="button"
                class="w-full h-full p-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 hover:border-amber-500/50 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer text-center min-h-[6.25rem]"
                @click="emit('select', item.key)"
              >
                <div class="h-8 w-8 rounded-lg bg-amber-500/20 group-hover:bg-amber-500 flex items-center justify-center text-amber-500 group-hover:text-white transition-colors shrink-0">
                  <Icon :name="item.icon" class="size-4" aria-hidden="true" />
                </div>
                <span class="text-xs font-bold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="item.label">
                  {{ item.label }}
                </span>
                <span
                  class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                  :class="getMockupCount(item.key) > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-white text-muted-foreground border border-border'"
                >
                  {{ getMockupCount(item.key) }} {{ getMockupCount(item.key) === 1 ? 'mockup' : 'mockups' }}
                </span>
              </button>
            </div>
          </div>

          <div v-else-if="!isGeneratingIdeas" class="py-10 text-center space-y-2">
            <div class="h-10 w-10 rounded-full bg-amber-100 text-amber-600 mx-auto flex items-center justify-center">
              <Icon name="lucide:sparkles" class="size-5" aria-hidden="true" />
            </div>
            <p class="text-xs font-medium text-foreground">No AI product recommendations yet</p>
            <p class="text-xs text-muted-foreground max-w-sm mx-auto">
              Click <b>Generate Ideas</b> to query AI for best-selling physical products that match your design.
            </p>
          </div>
        </div>

        <!-- TAB 3: Custom Library Categories -->
        <div v-else-if="activeTab === 'custom'" class="space-y-3">
          <p class="text-xs text-muted-foreground">
            Custom product categories uploaded to your Mockup Library:
          </p>
          <div v-if="customItems.length > 0" class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in customItems"
              :key="item.key"
              type="button"
              class="p-2.5 rounded-xl border border-[#FFDCC7] bg-secondary/50 hover:bg-secondary hover:border-primary/50 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[6.25rem]"
              @click="emit('select', item.key)"
            >
              <div class="h-8 w-8 rounded-lg bg-white border border-[#FFDCC7] flex items-center justify-center text-primary transition-colors shrink-0">
                <Icon :name="item.icon" class="size-4" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="item.label">
                {{ item.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="getMockupCount(item.key) > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-muted text-muted-foreground border border-border'"
              >
                {{ getMockupCount(item.key) }} {{ getMockupCount(item.key) === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>
        </div>

        <!-- TAB 4: All Catalog -->
        <div v-else-if="activeTab === 'all'" class="space-y-3">
          <p class="text-xs text-muted-foreground">
            Standard supported product catalog:
          </p>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="p in allCatalogItems"
              :key="p.key"
              type="button"
              class="p-2.5 rounded-xl border border-border hover:border-primary/50 hover:bg-secondary/40 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[6.25rem]"
              @click="emit('select', p.key)"
            >
              <div class="h-8 w-8 rounded-lg bg-secondary/60 group-hover:bg-secondary flex items-center justify-center text-secondary-foreground group-hover:text-primary transition-colors shrink-0">
                <Icon :name="p.icon" class="size-4" aria-hidden="true" />
              </div>
              <span class="text-xs font-semibold text-foreground line-clamp-2 leading-tight break-words px-0.5 text-center" :title="p.label">
                {{ p.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="getMockupCount(p.key) > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-secondary text-muted-foreground border border-border'"
              >
                {{ getMockupCount(p.key) }} {{ getMockupCount(p.key) === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>
        </div>
      </div>

      <!-- 4. Modal Footer -->
      <div class="px-5 py-3 border-t border-border bg-slate-50/50 flex items-center justify-between text-xs text-muted-foreground shrink-0">
        <span class="text-[11px]">Need a blank template or custom product?</span>
        <NuxtLink
          to="/library"
          class="text-primary-hover hover:text-[#B33E0B] font-semibold inline-flex items-center gap-1 hover:underline cursor-pointer"
          @click="emit('close')"
        >
          <span>Mockup Library</span>
          <Icon name="lucide:arrow-right" class="size-3" aria-hidden="true" />
        </NuxtLink>
      </div>
    </div>
  </div>
</template>
