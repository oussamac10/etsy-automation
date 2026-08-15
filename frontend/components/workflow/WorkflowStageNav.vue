<script setup lang="ts">
import { computed } from "vue";
import {
  FileText,
  Sparkles,
  Palette,
  Printer,
  CheckCircle2,
  RotateCw,
  AlertCircle,
} from "lucide-vue-next";
import Badge from "~/components/ui/Badge.vue";

const props = defineProps<{
  activeTab: string;
  workflowState: string;
  conceptsCount: number;
  candidatesCount: number;
  productionStatus?: string | null;
}>();

const emit = defineEmits<{
  (e: "update:activeTab", tab: string): void;
}>();

const isGate1Done = computed(() => {
  return [
    "IDEA_APPROVED",
    "ART_QUEUED",
    "ART_GENERATION",
    "ART_REVIEW",
    "ARTWORK_APPROVED",
    "PRODUCTION",
    "IP_REVIEW",
    "LISTING_REVIEW",
    "PUBLISHED",
  ].includes(props.workflowState);
});

const isGate2Done = computed(() => {
  return [
    "ARTWORK_APPROVED",
    "PRODUCTION",
    "IP_REVIEW",
    "LISTING_REVIEW",
    "PUBLISHED",
  ].includes(props.workflowState) || props.productionStatus === "SUCCEEDED";
});

const isProductionDone = computed(() => {
  return props.productionStatus === "SUCCEEDED";
});

const isResearchActive = computed(() => {
  return ["RESEARCH_QUEUED", "RESEARCHING"].includes(props.workflowState);
});

const isArtActive = computed(() => {
  return ["ART_QUEUED", "ART_GENERATION"].includes(props.workflowState);
});

const isProductionActive = computed(() => {
  return props.workflowState === "PRODUCTION" || props.productionStatus === "RUNNING" || props.productionStatus === "QUEUED";
});
</script>

<template>
  <nav class="border-b border-zinc-200 bg-white/70 backdrop-blur-md sticky top-0 z-10 rounded-xl shadow-2xs p-1.5 flex items-center gap-1.5 overflow-x-auto">
    <!-- Tab 1: Overview -->
    <button
      type="button"
      class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap"
      :class="
        activeTab === 'overview'
          ? 'bg-zinc-900 text-white shadow-xs'
          : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
      "
      @click="emit('update:activeTab', 'overview')"
    >
      <FileText class="h-4 w-4" />
      <span>Overview & Brief</span>
    </button>

    <!-- Tab 2: Concepts & Research -->
    <button
      type="button"
      class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap relative"
      :class="
        activeTab === 'concepts'
          ? 'bg-zinc-900 text-white shadow-xs'
          : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
      "
      @click="emit('update:activeTab', 'concepts')"
    >
      <RotateCw v-if="isResearchActive" class="h-3.5 w-3.5 animate-spin text-amber-500" />
      <CheckCircle2 v-else-if="isGate1Done" class="h-3.5 w-3.5 text-emerald-500" />
      <Sparkles v-else class="h-4 w-4 text-indigo-500" />
      <span>1. Concepts & Research</span>
      <span
        v-if="conceptsCount > 0"
        class="text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold"
        :class="activeTab === 'concepts' ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-200 text-zinc-700'"
      >
        {{ conceptsCount }}
      </span>
    </button>

    <!-- Tab 3: Artwork Studio -->
    <button
      type="button"
      class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap"
      :class="
        activeTab === 'artwork'
          ? 'bg-zinc-900 text-white shadow-xs'
          : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
      "
      @click="emit('update:activeTab', 'artwork')"
    >
      <RotateCw v-if="isArtActive" class="h-3.5 w-3.5 animate-spin text-amber-500" />
      <CheckCircle2 v-else-if="isGate2Done" class="h-3.5 w-3.5 text-emerald-500" />
      <Palette v-else class="h-4 w-4 text-indigo-500" />
      <span>2. Artwork Studio</span>
      <span
        v-if="candidatesCount > 0"
        class="text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold"
        :class="activeTab === 'artwork' ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-200 text-zinc-700'"
      >
        {{ candidatesCount }}
      </span>
    </button>

    <!-- Tab 4: Production & Mockups -->
    <button
      type="button"
      class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap"
      :class="
        activeTab === 'production'
          ? 'bg-zinc-900 text-white shadow-xs'
          : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
      "
      @click="emit('update:activeTab', 'production')"
    >
      <RotateCw v-if="isProductionActive" class="h-3.5 w-3.5 animate-spin text-amber-500" />
      <CheckCircle2 v-else-if="isProductionDone" class="h-3.5 w-3.5 text-emerald-500" />
      <Printer v-else class="h-4 w-4 text-indigo-500" />
      <span>3. Production & Mockups</span>
      <Badge
        v-if="isProductionDone"
        variant="success"
        class="text-[9px] px-1.5 py-0 font-bold uppercase tracking-wider"
      >
        Ready
      </Badge>
    </button>
  </nav>
</template>
