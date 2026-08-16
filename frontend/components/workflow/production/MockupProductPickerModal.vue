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
    <div class="bg-white rounded-2xl max-w-md w-full shadow-2xl overflow-hidden border border-zinc-200 animate-in fade-in zoom-in-95 duration-150">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
        <div>
          <h3 class="text-sm font-bold text-zinc-900">Select Product Type</h3>
          <p class="text-xs text-zinc-500">Choose a product category from your library to add mockups for</p>
        </div>
        <button
          type="button"
          class="h-8 w-8 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
        <!-- Active Custom Categories (from Library) -->
        <div v-if="customCategories.length > 0" class="space-y-2">
          <label class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider block">
            Custom Categories (From Library)
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="customKey in customCategories"
              :key="customKey"
              type="button"
              class="p-3 rounded-xl border border-indigo-200 bg-indigo-50/30 hover:bg-indigo-50 hover:border-indigo-500 flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', customKey)"
            >
              <div class="h-9 w-9 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600 transition-colors">
                <Icon :name="getProductIconName(customKey)" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-bold text-indigo-950 truncate max-w-full">
                {{ getProductLabel(customKey) }}
              </span>
            </button>
          </div>
        </div>

        <!-- Standard Products Grid -->
        <div class="space-y-2">
          <label v-if="customCategories.length > 0" class="text-[11px] font-bold text-zinc-500 uppercase tracking-wider block">
            Standard Products
          </label>
          <div class="grid grid-cols-3 gap-2.5">
            <button
              v-for="p in SUPPORTED_PRODUCT_TYPES"
              :key="p.key"
              type="button"
              class="p-3 rounded-xl border border-zinc-200 hover:border-indigo-500 hover:bg-indigo-50/40 flex flex-col items-center gap-1.5 transition-all cursor-pointer group text-center"
              @click="emit('select', p.key)"
            >
              <div class="h-9 w-9 rounded-lg bg-zinc-100 group-hover:bg-indigo-100 flex items-center justify-center text-zinc-600 group-hover:text-indigo-600 transition-colors">
                <Icon :name="p.icon" class="size-4.5" aria-hidden="true" />
              </div>
              <span class="text-xs font-semibold text-zinc-800 group-hover:text-indigo-950 truncate max-w-full">
                {{ p.label }}
              </span>
            </button>
          </div>
        </div>

        <!-- Library Link Footer -->
        <div class="pt-3 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-500">
          <span>Manage or add custom categories:</span>
          <NuxtLink
            to="/library"
            class="text-indigo-600 hover:text-indigo-700 font-semibold inline-flex items-center gap-1 hover:underline cursor-pointer"
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
