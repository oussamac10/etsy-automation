<script setup lang="ts">
import { computed, onMounted } from "vue";
import type { MockupAsset } from "~/types/mockup";
import {
  SUPPORTED_PRODUCT_TYPES,
  getProductLabel,
  getProductIconName,
  normalizeProductKey,
} from "~/utils/mockupProducts";
import { useLibraryProducts } from "~/composables/useLibraryProducts";

const props = defineProps<{
  open: boolean;
  existingCategories?: string[];
  recommendedCategories?: string[];
  mockupsByProduct?: Record<string, MockupAsset[]>;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "select", productKey: string): void;
}>();

const { libraryProductOptions, fetchLibraryProducts } = useLibraryProducts();

onMounted(() => {
  fetchLibraryProducts();
});

function getMockupCount(key: string): number {
  if (!props.mockupsByProduct) return 0;
  const normalized = normalizeProductKey(key);
  return (props.mockupsByProduct[normalized] || []).length;
}

// Recommended product items (from campaign intended physical products & AI prompt ideas)
const recommendedItems = computed(() => {
  const recSet = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string; count: number }> = [];

  for (const c of props.recommendedCategories || []) {
    const k = normalizeProductKey(c);
    if (k && !recSet.has(k)) {
      recSet.add(k);
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

// Standard products not already listed in recommended
const otherStandardItems = computed(() => {
  const recSet = new Set(recommendedItems.value.map((i) => i.key));
  return SUPPORTED_PRODUCT_TYPES.filter((p) => !recSet.has(p.key)).map((p) => ({
    key: p.key,
    label: p.label,
    icon: p.icon,
    count: getMockupCount(p.key),
  }));
});

// Custom categories from library or workflow mockups that are not standard
const customItems = computed(() => {
  const standardKeys = new Set(SUPPORTED_PRODUCT_TYPES.map((p) => p.key));
  const recKeys = new Set(recommendedItems.value.map((i) => i.key));
  const set = new Set<string>();
  const items: Array<{ key: string; label: string; icon: string; count: number }> = [];

  // From library
  for (const opt of libraryProductOptions.value) {
    if (opt.isCustom && !standardKeys.has(opt.value)) {
      const k = normalizeProductKey(opt.value);
      if (k && !set.has(k) && !recKeys.has(k)) {
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

  // From existing mockups
  if (props.existingCategories) {
    for (const c of props.existingCategories) {
      const k = normalizeProductKey(c);
      if (k && !standardKeys.has(k) && !set.has(k) && !recKeys.has(k)) {
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
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
    <div class="bg-white rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden border border-border animate-in fade-in zoom-in-95 duration-150">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
        <div>
          <h3 class="text-sm font-bold text-foreground">Select Product Type</h3>
          <p class="text-xs text-muted-foreground">Choose a product category to add or manage realistic mockups</p>
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
      <div class="p-6 space-y-5 max-h-[72vh] overflow-y-auto">
        <!-- Section 1: Campaign & AI Concept Suggestions (Shown First!) -->
        <div v-if="recommendedItems.length > 0" class="space-y-2.5">
          <div class="flex items-center gap-1.5">
            <Icon name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
            <label class="text-[11px] font-bold text-foreground uppercase tracking-wider block">
              Recommended For This Campaign & Concept
            </label>
          </div>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in recommendedItems"
              :key="item.key"
              type="button"
              class="relative p-3 rounded-xl border border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', item.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-primary/10 group-hover:bg-primary flex items-center justify-center text-primary group-hover:text-white transition-colors">
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-foreground truncate max-w-full">
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

        <!-- Section 2: Custom Categories (From Library) -->
        <div v-if="customItems.length > 0" class="space-y-2.5">
          <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            Custom Library Categories
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="item in customItems"
              :key="item.key"
              type="button"
              class="p-3 rounded-xl border border-[#FFDCC7] bg-secondary/50 hover:bg-secondary hover:border-primary/50 flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', item.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-white border border-[#FFDCC7] flex items-center justify-center text-primary transition-colors">
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-foreground truncate max-w-full">
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

        <!-- Section 3: All Other Product Categories -->
        <div class="space-y-2.5">
          <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            {{ recommendedItems.length > 0 ? 'Other Product Categories' : 'All Product Categories' }}
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="p in otherStandardItems"
              :key="p.key"
              type="button"
              class="p-3 rounded-xl border border-border hover:border-primary/50 hover:bg-secondary/40 flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', p.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-secondary/60 group-hover:bg-secondary flex items-center justify-center text-secondary-foreground group-hover:text-primary transition-colors">
                <Icon :name="p.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-semibold text-foreground truncate max-w-full">
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
