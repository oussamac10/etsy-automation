<script setup lang="ts">
import { computed, ref, onMounted } from "vue";
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
});

const isGeneratingIdeas = ref(false);
const generateError = ref<string | null>(null);
const aiGeneratedItems = ref<Array<{ key: string; label: string; icon: string; count: number }>>([]);

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

// 1. Campaign's Intended Physical Products
const campaignItems = computed(() => {
  const seen = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string; count: number }> = [];

  for (const c of props.campaignProducts || []) {
    const k = normalizeProductKey(c);
    if (k && !seen.has(k)) {
      seen.add(k);
      items.push({
        key: k,
        label: getProductLabel(k),
        icon: getProductIconName(k),
        count: getMockupCount(k),
      });
    }
  }

  return items;
});

// 2. Other Standard Categories (excluding campaign target products & dynamically generated ideas)
const otherStandardItems = computed(() => {
  const chosenKeys = new Set([
    ...campaignItems.value.map((i) => i.key),
    ...aiGeneratedItems.value.map((i) => i.key),
  ]);
  return SUPPORTED_PRODUCT_TYPES.filter((p) => !chosenKeys.has(p.key)).map((p) => ({
    key: p.key,
    label: p.label,
    icon: p.icon,
    count: getMockupCount(p.key),
  }));
});

// 3. Custom categories from library or workflow mockups
const customItems = computed(() => {
  const standardKeys = new Set(SUPPORTED_PRODUCT_TYPES.map((p) => p.key));
  const chosenKeys = new Set([
    ...campaignItems.value.map((i) => i.key),
    ...aiGeneratedItems.value.map((i) => i.key),
  ]);
  const set = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string; count: number }> = [];

  for (const opt of libraryProductOptions.value) {
    if (opt.isCustom && !standardKeys.has(opt.value)) {
      const k = normalizeProductKey(opt.value);
      if (k && !set.has(k) && !chosenKeys.has(k)) {
        set.add(k);
        items.push({
          key: k,
          label: getProductLabel(k),
          icon: getProductIconName(k),
          count: getMockupCount(k),
        });
      }
    }
  }

  return items;
});

// Generate AI Mockup Product Ideas on demand when the user clicks the button
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
      const items: Array<{ key: string; label: string; icon: string; count: number }> = [];

      for (const s of res.suggestions) {
        const clean = String(s).trim().replace(/^['"\[\]\s]+|['"\[\]\s]+$/g, "");
        const k = normalizeProductKey(clean);
        if (k && !campaignKeys.has(k) && !seen.has(k)) {
          seen.add(k);
          items.push({
            key: k,
            label: getProductLabel(clean),
            icon: getProductIconName(k),
            count: getMockupCount(k),
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

function removeAiIdea(key: string) {
  aiGeneratedItems.value = aiGeneratedItems.value.filter((item) => item.key !== key);
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
    <div class="bg-white rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden border border-border animate-in fade-in zoom-in-95 duration-150">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
        <div>
          <h3 class="text-sm font-bold text-foreground">Select Product Type</h3>
          <p class="text-xs text-muted-foreground">Choose a product category to add or composite mockups</p>
        </div>
        <button
          type="button"
          class="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
        <!-- Section 1: Campaign Intended Physical Products -->
        <div v-if="campaignItems.length > 0" class="space-y-2.5">
          <div class="flex items-center gap-1.5">
            <Icon name="lucide:check-circle-2" class="size-3.5 text-primary" aria-hidden="true" />
            <label class="text-[11px] font-bold text-foreground uppercase tracking-wider block">
              Campaign Intended Products (Target)
            </label>
          </div>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in campaignItems"
              :key="item.key"
              type="button"
              class="relative p-3 rounded-xl border border-primary/50 bg-primary/5 hover:bg-primary/10 hover:border-primary flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[7.5rem]"
              @click="emit('select', item.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-primary/10 group-hover:bg-primary flex items-center justify-center text-primary group-hover:text-white transition-colors shrink-0">
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span
                class="text-xs font-bold text-foreground line-clamp-2 min-h-[2rem] flex items-center justify-center leading-tight break-words px-0.5 text-center"
                :title="item.label"
              >
                {{ item.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="item.count > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-white text-muted-foreground border border-border'"
              >
                {{ item.count }} {{ item.count === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>
        </div>

        <!-- Section 2: On-Demand AI Mockup Ideas Trigger & Results -->
        <div class="space-y-2.5">
          <div class="flex items-center justify-between gap-2">
            <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Icon name="lucide:sparkles" class="size-3.5 text-amber-500" aria-hidden="true" />
              <span>AI Product Recommendations</span>
            </label>
            <div class="flex items-center gap-1.5">
              <Button
                v-if="aiGeneratedItems.length > 0"
                variant="ghost"
                size="sm"
                class="h-7 text-xs text-muted-foreground hover:text-red-600 hover:bg-red-50 gap-1 px-2 cursor-pointer"
                title="Clear all AI ideas"
                @click="aiGeneratedItems = []"
              >
                <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                <span>Clear</span>
              </Button>
              <Button
                v-if="workflowId"
                variant="outline"
                size="sm"
                class="h-7 text-xs font-bold border-amber-300 bg-amber-50/50 hover:bg-amber-100 text-amber-900 gap-1.5 cursor-pointer shadow-2xs"
                :disabled="isGeneratingIdeas"
                @click="handleGenerateAiIdeas"
              >
                <Icon
                  :name="isGeneratingIdeas ? 'lucide:loader-2' : 'lucide:sparkles'"
                  class="size-3"
                  :class="{ 'animate-spin': isGeneratingIdeas }"
                  aria-hidden="true"
                />
                <span>{{ isGeneratingIdeas ? 'Generating Ideas...' : aiGeneratedItems.length > 0 ? 'Regenerate Ideas' : 'Generate Mockup Ideas' }}</span>
              </Button>
            </div>
          </div>

          <!-- Error Alert if generation failed -->
          <div v-if="generateError" class="p-2.5 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
            {{ generateError }}
          </div>

          <!-- Dynamic AI Generated Cards -->
          <div v-if="aiGeneratedItems.length > 0" class="grid grid-cols-3 gap-2.5 animate-in fade-in zoom-in-95 duration-200">
            <div
              v-for="item in aiGeneratedItems"
              :key="item.key"
              class="relative group"
            >
              <!-- Delete Option Button for AI Idea -->
              <button
                type="button"
                class="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-white border border-amber-300 text-muted-foreground hover:text-red-600 hover:border-red-400 hover:bg-red-50 flex items-center justify-center shadow-xs transition-colors z-10 cursor-pointer"
                title="Delete this mockup idea"
                @click.stop="removeAiIdea(item.key)"
              >
                <Icon name="lucide:x" class="size-3" aria-hidden="true" />
              </button>

              <button
                type="button"
                class="w-full h-full p-3 rounded-xl border border-amber-300/80 bg-amber-50/60 hover:bg-amber-100/70 hover:border-amber-400 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer text-center min-h-[7.5rem]"
                @click="emit('select', item.key)"
              >
                <div class="h-9 w-9 rounded-lg bg-amber-200/70 group-hover:bg-amber-500 flex items-center justify-center text-amber-900 group-hover:text-white transition-colors shrink-0">
                  <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
                </div>
                <span
                  class="text-xs font-bold text-foreground line-clamp-2 min-h-[2rem] flex items-center justify-center leading-tight break-words px-0.5 text-center"
                  :title="item.label"
                >
                  {{ item.label }}
                </span>
                <span
                  class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                  :class="item.count > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-white text-muted-foreground border border-border'"
                >
                  {{ item.count }} {{ item.count === 1 ? 'mockup' : 'mockups' }}
                </span>
              </button>
            </div>
          </div>
          <div v-else-if="!isGeneratingIdeas" class="p-3 rounded-xl border border-dashed border-border bg-secondary/20 text-center">
            <p class="text-xs text-muted-foreground">
              Click <b>Generate Mockup Ideas</b> to let AI suggest fresh, top-selling product categories for this design.
            </p>
          </div>
        </div>

        <!-- Section 3: Custom Categories (From Library) -->
        <div v-if="customItems.length > 0" class="space-y-2.5">
          <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            Custom Library Categories
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in customItems"
              :key="item.key"
              type="button"
              class="p-3 rounded-xl border border-[#FFDCC7] bg-secondary/50 hover:bg-secondary hover:border-primary/50 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[7.5rem]"
              @click="emit('select', item.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-white border border-[#FFDCC7] flex items-center justify-center text-primary transition-colors shrink-0">
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span
                class="text-xs font-bold text-foreground line-clamp-2 min-h-[2rem] flex items-center justify-center leading-tight break-words px-0.5 text-center"
                :title="item.label"
              >
                {{ item.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="item.count > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-muted text-muted-foreground border border-border'"
              >
                {{ item.count }} {{ item.count === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>
        </div>

        <!-- Section 4: All Other Product Categories -->
        <div class="space-y-2.5">
          <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            All Product Categories
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="p in otherStandardItems"
              :key="p.key"
              type="button"
              class="p-3 rounded-xl border border-border hover:border-primary/50 hover:bg-secondary/40 flex flex-col items-center justify-between gap-1.5 transition-all cursor-pointer group text-center min-h-[7.5rem]"
              @click="emit('select', p.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-secondary/60 group-hover:bg-secondary flex items-center justify-center text-secondary-foreground group-hover:text-primary transition-colors shrink-0">
                <Icon :name="p.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span
                class="text-xs font-semibold text-foreground line-clamp-2 min-h-[2rem] flex items-center justify-center leading-tight break-words px-0.5 text-center"
                :title="p.label"
              >
                {{ p.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                :class="p.count > 0 ? 'bg-emerald-100 text-emerald-800 font-bold border border-emerald-300' : 'bg-secondary text-muted-foreground border border-border'"
              >
                {{ p.count }} {{ p.count === 1 ? 'mockup' : 'mockups' }}
              </span>
            </button>
          </div>
        </div>

        <!-- Library Link Footer -->
        <div class="pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
          <span>Manage or add custom categories:</span>
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
  </div>
</template>
