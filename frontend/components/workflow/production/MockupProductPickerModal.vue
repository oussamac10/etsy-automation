<script setup lang="ts">
import { computed, onMounted } from "vue";
import { SUPPORTED_PRODUCT_TYPES, getProductLabel, getProductIconName, normalizeProductKey } from "~/utils/mockupProducts";
import { useLibraryProducts } from "~/composables/useLibraryProducts";

const props = defineProps<{
  open: boolean;
  existingCategories?: string[];
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "select", productKey: string): void;
}>();

const { libraryProductOptions, fetchLibraryProducts } = useLibraryProducts();

onMounted(() => {
  fetchLibraryProducts();
});

// Extract custom categories that come from the library or existing workflow mockups
const customCategories = computed(() => {
  const standardKeys = new Set(SUPPORTED_PRODUCT_TYPES.map((p) => p.key));
  const set = new Set<string>();

  // Custom categories from library
  for (const opt of libraryProductOptions.value) {
    if (opt.isCustom && !standardKeys.has(opt.value)) {
      set.add(normalizeProductKey(opt.value));
    }
  }

  // Custom categories from existing workflow mockups
  if (props.existingCategories) {
    for (const c of props.existingCategories) {
      const k = normalizeProductKey(c);
      if (k && !standardKeys.has(k)) {
        set.add(k);
      }
    }
  }

  return Array.from(set);
});
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
    <div class="bg-white rounded-2xl max-w-md w-full shadow-2xl overflow-hidden border border-border animate-in fade-in zoom-in-95 duration-150">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
        <div>
          <h3 class="text-sm font-bold text-foreground">Select Product Type</h3>
          <p class="text-xs text-muted-foreground">Choose a product category from your library to add mockups for</p>
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
      <div class="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
        <!-- Active Custom Categories (from Library) -->
        <div v-if="customCategories.length > 0" class="space-y-2">
          <label class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            Custom Categories (From Library)
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="customKey in customCategories"
              :key="customKey"
              type="button"
              class="p-3 rounded-xl border border-[#FFDCC7] bg-secondary/50 hover:bg-secondary hover:border-primary/50 flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', customKey)"
            >
              <div class="h-9 w-9 rounded-lg bg-white border border-[#FFDCC7] flex items-center justify-center text-primary transition-colors">
                <Icon :name="getProductIconName(customKey)" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-foreground truncate max-w-full">
                {{ getProductLabel(customKey) }}
              </span>
            </button>
          </div>
        </div>

        <!-- Standard Products Grid -->
        <div class="space-y-2">
          <label v-if="customCategories.length > 0" class="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
            Standard Products
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="p in SUPPORTED_PRODUCT_TYPES"
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
