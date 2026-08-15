<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import Badge from "./Badge.vue";

interface ProductOption {
  value: string;
  label: string;
  icon: string;
}

const DEFAULT_PRODUCTS: ProductOption[] = [
  { value: "mug", label: "Ceramic Mug", icon: "lucide:coffee" },
  { value: "tshirt", label: "T-Shirt", icon: "lucide:shirt" },
  { value: "sweatshirt", label: "Sweatshirt / Hoodie", icon: "lucide:shirt" },
  { value: "tote_bag", label: "Tote Bag", icon: "lucide:shopping-bag" },
  { value: "tumbler", label: "Tumbler / Cup", icon: "lucide:cup-soda" },
  { value: "poster", label: "Poster / Wall Art", icon: "lucide:image" },
  { value: "sticker", label: "Stickers", icon: "lucide:tags" },
  { value: "phone_case", label: "Phone Case", icon: "lucide:smartphone" },
  { value: "candle", label: "Scented Candle", icon: "lucide:flame" },
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
  return { value: val, label: val, icon: "lucide:package" };
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
  return !DEFAULT_PRODUCTS.some(
    (p) => p.label.toLowerCase() === query || p.value.toLowerCase() === query
  );
});

function isSelected(val: string): boolean {
  return props.modelValue.some((v) => v.toLowerCase() === val.toLowerCase());
}

function toggleProduct(val: string) {
  const current = [...props.modelValue];
  const idx = current.findIndex((v) => v.toLowerCase() === val.toLowerCase());
  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(val);
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

  const current = [...props.modelValue];
  if (!current.some((v) => v.toLowerCase() === query.toLowerCase())) {
    current.push(query);
    emit("update:modelValue", current);
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
    <!-- Trigger Button / Box -->
    <div
      class="min-h-9 w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 shadow-2xs transition-colors focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 flex flex-wrap items-center gap-1.5 cursor-pointer"
      @click="isOpen = true"
    >
      <!-- Selected tags -->
      <span
        v-for="item in modelValue"
        :key="item"
        class="inline-flex items-center gap-1.5 rounded-md bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-800 shadow-3xs hover:bg-zinc-200/80 transition-colors"
      >
        <Icon :name="getProductInfo(item).icon" class="size-3 text-zinc-500 shrink-0" aria-hidden="true" />
        <span>{{ getProductInfo(item).label }}</span>
        <button
          type="button"
          class="ml-0.5 rounded text-zinc-400 hover:text-zinc-700 focus:outline-hidden cursor-pointer"
          aria-label="Remove item"
          @click.stop="removeProduct(item)"
        >
          <Icon name="lucide:x" class="size-3" aria-hidden="true" />
        </button>
      </span>

      <!-- Search / Input box -->
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="modelValue.length === 0 ? placeholder : 'Add more...'"
        class="flex-1 min-w-[120px] bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-hidden h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <Icon name="lucide:chevron-down" class="size-3.5 text-zinc-400 transition-transform ml-auto shrink-0" :class="{ 'rotate-180': isOpen }" aria-hidden="true" />
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
          class="flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs text-left transition-colors hover:bg-zinc-100 cursor-pointer"
          :class="{ 'bg-indigo-50/80 font-medium text-indigo-900': isSelected(opt.value) }"
          @click="toggleProduct(opt.value)"
        >
          <div class="flex items-center gap-2">
            <Icon :name="opt.icon" class="size-3.5 text-zinc-500 shrink-0" aria-hidden="true" />
            <span>{{ opt.label }}</span>
            <span class="text-[10px] text-zinc-400 font-mono">({{ opt.value }})</span>
          </div>
          <Icon v-if="isSelected(opt.value)" name="lucide:check" class="size-3.5 text-indigo-600 font-bold" aria-hidden="true" />
        </button>

        <!-- Custom Item Option -->
        <button
          v-if="isCustomQueryNew"
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 font-semibold border-t border-zinc-100 mt-1 cursor-pointer"
          @click="addCustomItem"
        >
          <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
          <span>Add custom product "{{ searchQuery }}"</span>
        </button>
      </div>
    </transition>
  </div>
</template>
