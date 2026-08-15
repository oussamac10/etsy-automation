<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { Check, ChevronDown, Plus, X } from "lucide-vue-next";
import Badge from "./Badge.vue";

interface ProductOption {
  value: string;
  label: string;
  icon: string;
}

const DEFAULT_PRODUCTS: ProductOption[] = [
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

const props = withDefaults(
  defineProps<{
    modelValue: string[];
    placeholder?: string;
  }>(),
  {
    modelValue: () => [],
    placeholder: "Select or type physical products...",
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const isOpen = ref(false);
const searchQuery = ref("");
const containerRef = ref<HTMLElement | null>(null);

function getProductInfo(val: string): ProductOption {
  const found = DEFAULT_PRODUCTS.find(
    (p) => p.value.toLowerCase() === val.toLowerCase() || p.label.toLowerCase() === val.toLowerCase()
  );
  if (found) return found;
  return { value: val, label: val, icon: "📦" };
}

const filteredOptions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return DEFAULT_PRODUCTS;
  return DEFAULT_PRODUCTS.filter(
    (p) => p.label.toLowerCase().includes(query) || p.value.toLowerCase().includes(query)
  );
});

const isCustomQueryNew = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return false;
  const matchInCatalog = DEFAULT_PRODUCTS.some(
    (p) => p.value.toLowerCase() === query || p.label.toLowerCase() === query
  );
  const alreadySelected = props.modelValue.some((v) => v.toLowerCase() === query);
  return !matchInCatalog && !alreadySelected;
});

function isSelected(val: string): boolean {
  return props.modelValue.some((v) => v.toLowerCase() === val.toLowerCase());
}

function toggleProduct(val: string) {
  const normalized = val.trim();
  if (!normalized) return;

  const current = [...props.modelValue];
  const idx = current.findIndex((v) => v.toLowerCase() === normalized.toLowerCase());

  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(normalized);
  }
  emit("update:modelValue", current);
}

function removeProduct(val: string) {
  const current = props.modelValue.filter((v) => v.toLowerCase() !== val.toLowerCase());
  emit("update:modelValue", current);
}

function addCustomItem() {
  const query = searchQuery.value.trim();
  if (!query) return;
  if (!isSelected(query)) {
    toggleProduct(query);
  }
  searchQuery.value = "";
}

function handleClickOutside(event: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false;
  }
}

onMounted(() => {
  if (typeof document !== "undefined") {
    document.addEventListener("mousedown", handleClickOutside);
  }
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined") {
    document.removeEventListener("mousedown", handleClickOutside);
  }
});
</script>

<template>
  <div ref="containerRef" class="relative w-full text-xs">
    <!-- Trigger Input Container -->
    <div
      class="min-h-9 w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 shadow-2xs transition-colors focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 flex flex-wrap items-center gap-1.5 cursor-pointer"
      @click="isOpen = true"
    >
      <!-- Selected Tags -->
      <span
        v-for="item in modelValue"
        :key="item"
        class="inline-flex items-center gap-1 rounded-md bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-800 shadow-3xs hover:bg-zinc-200/80 transition-colors"
      >
        <span>{{ getProductInfo(item).icon }}</span>
        <span>{{ getProductInfo(item).label }}</span>
        <button
          type="button"
          class="ml-0.5 rounded text-zinc-400 hover:text-zinc-700 focus:outline-none"
          @click.stop="removeProduct(item)"
        >
          <X class="h-3 w-3" />
        </button>
      </span>

      <!-- Search / Input box -->
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="modelValue.length === 0 ? placeholder : 'Add more...'"
        class="flex-1 min-w-[120px] bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <ChevronDown class="h-3.5 w-3.5 text-zinc-400 transition-transform ml-auto shrink-0" :class="{ 'rotate-180': isOpen }" />
    </div>

    <!-- Dropdown Menu -->
    <transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
      <div
        v-if="isOpen"
        class="absolute left-0 top-full z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-zinc-200 bg-white p-1.5 shadow-lg space-y-0.5 text-zinc-800"
      >
        <div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          Catalog Products
        </div>

        <button
          v-for="opt in filteredOptions"
          :key="opt.value"
          type="button"
          class="flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs text-left transition-colors hover:bg-zinc-100"
          :class="{ 'bg-indigo-50/80 font-medium text-indigo-900': isSelected(opt.value) }"
          @click="toggleProduct(opt.value)"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm">{{ opt.icon }}</span>
            <span>{{ opt.label }}</span>
            <span class="text-[10px] text-zinc-400 font-mono">({{ opt.value }})</span>
          </div>
          <Check v-if="isSelected(opt.value)" class="h-3.5 w-3.5 text-indigo-600 font-bold" />
        </button>

        <!-- Custom Item Option -->
        <button
          v-if="isCustomQueryNew"
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 font-semibold border-t border-zinc-100 mt-1"
          @click="addCustomItem"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>Add custom product "{{ searchQuery }}"</span>
        </button>
      </div>
    </transition>
  </div>
</template>
