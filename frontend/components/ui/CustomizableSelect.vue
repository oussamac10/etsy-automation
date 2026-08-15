<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { Check, ChevronDown, Plus, Trash2, X } from "lucide-vue-next";

export interface SelectOption {
  value: string;
  label: string;
  icon?: string;
  isCustom?: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: string | string[];
    options: SelectOption[];
    storageKey?: string;
    placeholder?: string;
    isMulti?: boolean;
    id?: string;
  }>(),
  {
    storageKey: "",
    placeholder: "Select or type...",
    isMulti: false,
    id: "",
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | string[]): void;
}>();

const isOpen = ref(false);
const searchQuery = ref("");
const containerRef = ref<HTMLElement | null>(null);
const customOptions = ref<SelectOption[]>([]);

function loadCustomOptions() {
  if (!props.storageKey || typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(props.storageKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        customOptions.value = parsed.map((item) => {
          if (typeof item === "string") {
            return { value: item, label: item, icon: "✨", isCustom: true };
          }
          return { ...item, isCustom: true };
        });
      }
    }
  } catch (e) {
    console.error("Failed to load custom options from localStorage", e);
  }
}

function saveCustomOptions() {
  if (!props.storageKey || typeof window === "undefined") return;
  try {
    localStorage.setItem(props.storageKey, JSON.stringify(customOptions.value));
  } catch (e) {
    console.error("Failed to save custom options to localStorage", e);
  }
}

const allOptions = computed<SelectOption[]>(() => {
  const combined = [...props.options];
  for (const custom of customOptions.value) {
    if (!combined.some((o) => o.value.toLowerCase() === custom.value.toLowerCase())) {
      combined.push(custom);
    }
  }
  return combined;
});

const filteredOptions = computed<SelectOption[]>(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return allOptions.value;
  return allOptions.value.filter(
    (o) => o.label.toLowerCase().includes(query) || o.value.toLowerCase().includes(query)
  );
});

const isCustomQueryNew = computed(() => {
  const query = searchQuery.value.trim();
  if (!query) return false;
  const matchInAll = allOptions.value.some(
    (o) => o.value.toLowerCase() === query.toLowerCase() || o.label.toLowerCase() === query.toLowerCase()
  );
  return !matchInAll;
});

function getOptionInfo(val: string): SelectOption {
  const found = allOptions.value.find(
    (o) => o.value.toLowerCase() === val.toLowerCase() || o.label.toLowerCase() === val.toLowerCase()
  );
  if (found) return found;
  return { value: val, label: val, icon: "✨", isCustom: true };
}

function isSelected(val: string): boolean {
  if (props.isMulti) {
    const arr = Array.isArray(props.modelValue) ? props.modelValue : [];
    return arr.some((v) => v.toLowerCase() === val.toLowerCase());
  }
  return (
    typeof props.modelValue === "string" &&
    props.modelValue.toLowerCase() === val.toLowerCase()
  );
}

function selectOption(val: string) {
  const normalized = val.trim();
  if (!normalized) return;

  if (props.isMulti) {
    const current = Array.isArray(props.modelValue) ? [...props.modelValue] : [];
    const idx = current.findIndex((v) => v.toLowerCase() === normalized.toLowerCase());
    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      current.push(normalized);
    }
    emit("update:modelValue", current);
  } else {
    emit("update:modelValue", normalized);
    isOpen.value = false;
    searchQuery.value = "";
  }
}

function removeMultiItem(val: string) {
  if (!props.isMulti) return;
  const current = Array.isArray(props.modelValue) ? props.modelValue : [];
  const updated = current.filter((v) => v.toLowerCase() !== val.toLowerCase());
  emit("update:modelValue", updated);
}

function clearSingle() {
  emit("update:modelValue", "");
  searchQuery.value = "";
}

function addCustomItem() {
  const query = searchQuery.value.trim();
  if (!query) return;

  const newOption: SelectOption = {
    value: query,
    label: query,
    icon: "✨",
    isCustom: true,
  };

  if (!customOptions.value.some((o) => o.value.toLowerCase() === query.toLowerCase())) {
    customOptions.value.push(newOption);
    saveCustomOptions();
  }

  selectOption(query);
  searchQuery.value = "";
}

function deleteCustomOption(val: string, event: MouseEvent) {
  event.stopPropagation();
  customOptions.value = customOptions.value.filter((o) => o.value.toLowerCase() !== val.toLowerCase());
  saveCustomOptions();

  if (props.isMulti) {
    removeMultiItem(val);
  } else if (typeof props.modelValue === "string" && props.modelValue.toLowerCase() === val.toLowerCase()) {
    clearSingle();
  }
}

function handleClickOutside(event: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false;
  }
}

onMounted(() => {
  loadCustomOptions();
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
    <!-- Trigger for Multi-Select -->
    <div
      v-if="isMulti"
      :id="id"
      class="min-h-9 w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 shadow-2xs transition-colors focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 flex flex-wrap items-center gap-1.5 cursor-pointer"
      @click="isOpen = true"
    >
      <span
        v-for="item in (Array.isArray(modelValue) ? modelValue : [])"
        :key="item"
        class="inline-flex items-center gap-1 rounded-md bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-800 shadow-3xs hover:bg-zinc-200/80 transition-colors"
      >
        <span v-if="getOptionInfo(item).icon">{{ getOptionInfo(item).icon }}</span>
        <span>{{ getOptionInfo(item).label }}</span>
        <button
          type="button"
          class="ml-0.5 rounded text-zinc-400 hover:text-zinc-700 focus:outline-none"
          @click.stop="removeMultiItem(item)"
        >
          <X class="h-3 w-3" />
        </button>
      </span>

      <input
        v-model="searchQuery"
        type="text"
        :placeholder="(!modelValue || modelValue.length === 0) ? placeholder : 'Add more...'"
        class="flex-1 min-w-[100px] bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <ChevronDown class="h-3.5 w-3.5 text-zinc-400 transition-transform ml-auto shrink-0" :class="{ 'rotate-180': isOpen }" />
    </div>

    <!-- Trigger for Single Select -->
    <div
      v-else
      :id="id"
      class="h-9 w-full rounded-md border border-zinc-200 bg-white px-2.5 py-1 text-xs shadow-2xs transition-colors focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 flex items-center justify-between gap-2 cursor-pointer"
      @click="isOpen = true"
    >
      <div v-if="!isOpen && modelValue" class="flex items-center gap-1.5 truncate text-zinc-900 font-medium">
        <span v-if="getOptionInfo(String(modelValue)).icon" class="text-sm">
          {{ getOptionInfo(String(modelValue)).icon }}
        </span>
        <span class="truncate">{{ getOptionInfo(String(modelValue)).label }}</span>
      </div>

      <input
        v-if="isOpen || !modelValue"
        v-model="searchQuery"
        type="text"
        :placeholder="modelValue ? getOptionInfo(String(modelValue)).label : placeholder"
        class="w-full bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="modelValue && !isOpen"
          type="button"
          class="rounded p-0.5 text-zinc-400 hover:text-zinc-700 focus:outline-none"
          @click.stop="clearSingle"
        >
          <X class="h-3 w-3" />
        </button>
        <ChevronDown class="h-3.5 w-3.5 text-zinc-400 transition-transform" :class="{ 'rotate-180': isOpen }" />
      </div>
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
        <div class="flex items-center justify-between px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          <span>Suggestions</span>
          <span v-if="storageKey" class="text-[9px] lowercase font-normal text-zinc-400">auto-saved</span>
        </div>

        <button
          v-for="opt in filteredOptions"
          :key="opt.value"
          type="button"
          class="group flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs text-left transition-colors hover:bg-zinc-100"
          :class="{ 'bg-indigo-50/80 font-medium text-indigo-900': isSelected(opt.value) }"
          @click="selectOption(opt.value)"
        >
          <div class="flex items-center gap-2 truncate">
            <span v-if="opt.icon" class="text-sm shrink-0">{{ opt.icon }}</span>
            <span class="truncate">{{ opt.label }}</span>
            <span v-if="opt.isCustom" class="text-[9px] px-1 py-0.2 rounded bg-indigo-100 text-indigo-700 font-mono">custom</span>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button
              v-if="opt.isCustom"
              type="button"
              class="opacity-0 group-hover:opacity-100 p-0.5 rounded text-zinc-400 hover:text-rose-600 transition-opacity"
              title="Remove custom option"
              @click="deleteCustomOption(opt.value, $event)"
            >
              <Trash2 class="h-3 w-3" />
            </button>
            <Check v-if="isSelected(opt.value)" class="h-3.5 w-3.5 text-indigo-600 font-bold" />
          </div>
        </button>

        <!-- Custom Add Option -->
        <button
          v-if="isCustomQueryNew"
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 font-semibold border-t border-zinc-100 mt-1"
          @click="addCustomItem"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>Add & save "{{ searchQuery }}"</span>
        </button>
      </div>
    </transition>
  </div>
</template>
