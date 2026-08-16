<script setup lang="ts">
import type { MockupAsset } from "~/types/mockup";
import { getProductLabel, getProductIconName } from "~/utils/mockupProducts";

defineProps<{
  availableTabs: string[];
  selectedTab: string;
  mockupsByProduct: Record<string, MockupAsset[]>;
}>();

const emit = defineEmits<{
  (e: "selectTab", tab: string): void;
  (e: "openNewCategory"): void;
}>();
</script>

<template>
  <div class="flex items-center gap-1.5 border-b border-zinc-200 pb-2 overflow-x-auto">
    <button
      v-for="pKey in availableTabs"
      :key="pKey"
      type="button"
      class="px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap"
      :class="
        selectedTab === pKey
          ? 'bg-indigo-600 text-white shadow-2xs'
          : 'bg-zinc-100 hover:bg-zinc-200/80 text-zinc-600'
      "
      @click="emit('selectTab', pKey)"
    >
      <Icon :name="getProductIconName(pKey)" class="size-3.5" aria-hidden="true" />
      <span>{{ getProductLabel(pKey) }}</span>
      <span
        class="text-[10px] px-1.5 py-0.2 rounded-full"
        :class="selectedTab === pKey ? 'bg-indigo-800 text-white' : 'bg-zinc-200 text-zinc-700'"
      >
        {{ (mockupsByProduct[pKey] || []).length }}
      </span>
    </button>

    <!-- + New Category Tab Button -->
    <button
      type="button"
      class="px-2.5 py-1.5 rounded-lg text-xs font-medium border border-dashed border-zinc-300 text-zinc-500 hover:text-indigo-600 hover:border-indigo-400 hover:bg-indigo-50/50 flex items-center gap-1 transition-colors cursor-pointer whitespace-nowrap"
      @click="emit('openNewCategory')"
    >
      <Icon name="lucide:plus" class="size-3" aria-hidden="true" />
      <span>New Category</span>
    </button>
  </div>
</template>
