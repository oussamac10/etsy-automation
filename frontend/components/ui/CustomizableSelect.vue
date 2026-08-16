<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";

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
    allowCustom?: boolean;
  }>(),
  {
    storageKey: "",
    placeholder: "Select or type...",
    isMulti: false,
    id: "",
    allowCustom: true,
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string | string[]): void;
}>();

const isOpen = ref(false);
const searchQuery = ref("");
const containerRef = ref<HTMLElement | null>(null);
const customOptions = ref<SelectOption[]>([]);

function isIconifyName(icon?: string): boolean {
  return Boolean(icon && (icon.startsWith("lucide:") || icon.includes(":")));
}

function loadCustomOptions() {
  if (!props.allowCustom || !props.storageKey || typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(props.storageKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        customOptions.value = parsed.map((item) => {
          if (typeof item === "string") {
            return { value: item, label: item, icon: "lucide:sparkles", isCustom: true };
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
  if (!props.allowCustom || !props.storageKey || typeof window === "undefined") return;
  try {
    localStorage.setItem(props.storageKey, JSON.stringify(customOptions.value));
  } catch (e) {
    console.error("Failed to save custom options to localStorage", e);
  }
}

const allOptions = computed<SelectOption[]>(() => {
  const combined = [...props.options];
  if (props.allowCustom) {
    for (const custom of customOptions.value) {
      if (!combined.some((o) => o.value.toLowerCase() === custom.value.toLowerCase())) {
        combined.push(custom);
      }
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
  if (!props.allowCustom) return false;
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
  return { value: val, label: val, icon: "lucide:sparkles", isCustom: true };
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
  if (!Array.isArray(props.modelValue)) return;
  const current = props.modelValue.filter((v) => v.toLowerCase() !== val.toLowerCase());
  emit("update:modelValue", current);
}

function addCustomItem() {
  const query = searchQuery.value.trim();
  if (!query) return;

  // Add to custom options
  const newOption: SelectOption = {
    value: query,
    label: query,
    icon: "lucide:sparkles",
    isCustom: true,
  };

  if (!customOptions.value.some((o) => o.value.toLowerCase() === query.toLowerCase())) {
    customOptions.value.push(newOption);
    saveCustomOptions();
  }

  // Select it
  selectOption(query);
  searchQuery.value = "";
}

function deleteCustomOption(val: string, event: MouseEvent) {
  event.stopPropagation();
  customOptions.value = customOptions.value.filter((o) => o.value.toLowerCase() !== val.toLowerCase());
  saveCustomOptions();

  // If currently selected, deselect it
  if (props.isMulti && Array.isArray(props.modelValue)) {
    emit(
      "update:modelValue",
      props.modelValue.filter((v) => v.toLowerCase() !== val.toLowerCase())
    );
  } else if (!props.isMulti && typeof props.modelValue === "string" && props.modelValue.toLowerCase() === val.toLowerCase()) {
    emit("update:modelValue", "");
  }
}

function clearSingle() {
  emit("update:modelValue", "");
  searchQuery.value = "";
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
        class="inline-flex items-center gap-1.5 rounded-md bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-800 shadow-3xs hover:bg-zinc-200/80 transition-colors"
      >
        <Icon
          v-if="isIconifyName(getOptionInfo(item).icon)"
          :name="getOptionInfo(item).icon!"
          class="size-3 text-zinc-500 shrink-0"
          aria-hidden="true"
        />
        <span>{{ getOptionInfo(item).label }}</span>
        <button
          type="button"
          class="ml-0.5 rounded text-zinc-400 hover:text-zinc-700 focus:outline-hidden cursor-pointer"
          aria-label="Remove item"
          @click.stop="removeMultiItem(item)"
        >
          <Icon name="lucide:x" class="size-3" aria-hidden="true" />
        </button>
      </span>

      <input
        v-model="searchQuery"
        type="text"
        :placeholder="(!modelValue || modelValue.length === 0) ? placeholder : ''"
        class="flex-1 min-w-[60px] bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-hidden h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <Icon name="lucide:chevron-down" class="size-3.5 text-zinc-400 transition-transform ml-auto shrink-0" :class="{ 'rotate-180': isOpen }" aria-hidden="true" />
    </div>

    <!-- Trigger for Single Select -->
    <div
      v-else
      :id="id"
      class="h-9 w-full rounded-md border border-zinc-200 bg-white px-2.5 py-1 text-xs shadow-2xs transition-colors focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 flex items-center justify-between gap-2 cursor-pointer"
      @click="isOpen = true"
    >
      <div v-if="!isOpen && modelValue" class="flex items-center gap-1.5 truncate text-zinc-900 font-medium">
        <Icon
          v-if="isIconifyName(getOptionInfo(String(modelValue)).icon)"
          :name="getOptionInfo(String(modelValue)).icon!"
          class="size-3.5 text-zinc-500 shrink-0"
          aria-hidden="true"
        />
        <span class="truncate">{{ getOptionInfo(String(modelValue)).label }}</span>
      </div>

      <input
        v-if="isOpen || !modelValue"
        v-model="searchQuery"
        type="text"
        :placeholder="modelValue ? getOptionInfo(String(modelValue)).label : placeholder"
        class="w-full bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-hidden h-6"
        @focus="isOpen = true"
        @keydown.enter.prevent="addCustomItem"
        @keydown.esc="isOpen = false"
      >

      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="modelValue && !isOpen"
          type="button"
          class="rounded p-0.5 text-zinc-400 hover:text-zinc-700 focus:outline-hidden cursor-pointer"
          aria-label="Clear selection"
          @click.stop="clearSingle"
        >
          <Icon name="lucide:x" class="size-3" aria-hidden="true" />
        </button>
        <Icon name="lucide:chevron-down" class="size-3.5 text-zinc-400 transition-transform" :class="{ 'rotate-180': isOpen }" aria-hidden="true" />
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
          class="group flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs text-left transition-colors hover:bg-zinc-100 cursor-pointer"
          :class="{ 'bg-indigo-50/80 font-medium text-indigo-900': isSelected(opt.value) }"
          @click="selectOption(opt.value)"
        >
          <div class="flex items-center gap-2 truncate">
            <Icon
              v-if="isIconifyName(opt.icon)"
              :name="opt.icon!"
              class="size-3.5 text-zinc-500 shrink-0"
              aria-hidden="true"
            />
            <span class="truncate">{{ opt.label }}</span>
            <span v-if="opt.isCustom" class="text-[9px] px-1 py-0.2 rounded bg-indigo-100 text-indigo-700 font-mono">custom</span>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button
              v-if="allowCustom && opt.isCustom && storageKey"
              type="button"
              class="opacity-0 group-hover:opacity-100 p-0.5 rounded text-zinc-400 hover:text-rose-600 transition-opacity cursor-pointer"
              aria-label="Remove custom option"
              title="Remove custom option"
              @click="deleteCustomOption(opt.value, $event)"
            >
              <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
            </button>
            <Icon v-if="isSelected(opt.value)" name="lucide:check" class="size-3.5 text-indigo-600 font-bold" aria-hidden="true" />
          </div>
        </button>

        <div v-if="filteredOptions.length === 0 && !isCustomQueryNew" class="px-3 py-3 text-xs text-zinc-400 text-center">
          No matching options found
        </div>

        <!-- Custom Add Option -->
        <button
          v-if="allowCustom && isCustomQueryNew"
          type="button"
          class="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 font-semibold border-t border-zinc-100 mt-1 cursor-pointer"
          @click="addCustomItem"
        >
          <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
          <span>Add & save "{{ searchQuery }}"</span>
        </button>
      </div>
    </transition>
  </div>
</template>
