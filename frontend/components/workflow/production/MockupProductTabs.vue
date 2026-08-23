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
  <div class="w-full min-w-0 max-w-full overflow-x-auto scrollbar-none overscroll-x-contain touch-pan-x border-b border-border pb-2">
    <div class="flex items-center gap-1.5 min-w-max">
      <button
        v-for="pKey in availableTabs"
        :key="pKey"
        type="button"
        class="px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap shrink-0 select-none"
        :class="
          selectedTab === pKey
            ? 'bg-primary text-white shadow-2xs'
            : 'bg-secondary hover:bg-secondary/80 text-secondary-foreground'
        "
        @click="emit('selectTab', pKey)"
      >
        <Icon :name="getProductIconName(pKey)" class="size-3.5 shrink-0" aria-hidden="true" />
        <span>{{ getProductLabel(pKey) }}</span>
        <span
          class="text-[10px] px-1.5 py-0.2 rounded-full shrink-0"
          :class="selectedTab === pKey ? 'bg-primary-hover text-white' : 'bg-card text-secondary-foreground border border-border'"
        >
          {{ (mockupsByProduct[pKey] || []).length }}
        </span>
      </button>

      <!-- + New Category Tab Button -->
      <button
        type="button"
        class="px-2.5 py-1.5 rounded-lg text-xs font-medium border border-dashed border-border text-muted-foreground hover:text-primary hover:border-primary/60 hover:bg-secondary/60 flex items-center gap-1 transition-colors cursor-pointer whitespace-nowrap shrink-0 select-none"
        @click="emit('openNewCategory')"
      >
        <Icon name="lucide:plus" class="size-3 shrink-0" aria-hidden="true" />
        <span>New Category</span>
      </button>
    </div>
  </div>
</template>
