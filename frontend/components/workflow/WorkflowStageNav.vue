<script setup lang="ts">
import { computed } from "vue";
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

const isGate3Done = computed(() => {
  return [
    "READY_FOR_ETSY_DRAFT",
    "ETSY_DRAFT_CREATED",
    "ETSY_DRAFT_FAILED",
    "PUBLISHED",
  ].includes(props.workflowState);
});

const isListingActive = computed(() => {
  return ["IP_REVIEW", "LISTING_REVIEW"].includes(props.workflowState);
});
</script>

<template>
  <nav class="border border-border bg-muted/70 backdrop-blur-md sticky top-12 sm:top-14 z-20 rounded-xl shadow-2xs p-1.5 w-full overflow-x-auto scrollbar-none overscroll-x-contain touch-pan-x" role="tablist" aria-label="Workflow Stages">
    <div class="flex items-center gap-1 min-w-max lg:min-w-0 lg:w-full lg:justify-between">
      <!-- Tab 1: Overview -->
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'overview'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'overview'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'overview')"
      >
        <Icon name="lucide:file-text" class="size-3.5 shrink-0" :class="activeTab === 'overview' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden md:inline">Overview &amp; Brief</span>
        <span class="truncate md:hidden">Overview</span>
      </button>

      <!-- Tab 2: Concepts & Research -->
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'concepts'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'concepts'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'concepts')"
      >
        <Icon v-if="isResearchActive" name="lucide:loader-circle" class="size-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
        <Icon v-else-if="isGate1Done" name="lucide:circle-check" class="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        <Icon v-else name="lucide:sparkles" class="size-3.5 shrink-0" :class="activeTab === 'concepts' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden 2xl:inline">1. Concepts &amp; Research</span>
        <span class="truncate 2xl:hidden">1. Concepts</span>
        <span
          v-if="conceptsCount > 0"
          class="text-[9px] px-1.5 py-0 rounded-full font-mono font-bold shrink-0"
          :class="activeTab === 'concepts' ? 'bg-primary/10 text-primary border border-primary/20' : 'bg-secondary text-secondary-foreground border border-border/50'"
        >
          {{ conceptsCount }}
        </span>
      </button>

      <!-- Tab 3: Artwork Studio -->
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'artwork'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'artwork'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'artwork')"
      >
        <Icon v-if="isArtActive" name="lucide:loader-circle" class="size-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
        <Icon v-else-if="isGate2Done" name="lucide:circle-check" class="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        <Icon v-else name="lucide:image" class="size-3.5 shrink-0" :class="activeTab === 'artwork' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden 2xl:inline">2. Artwork Studio</span>
        <span class="truncate 2xl:hidden">2. Artwork</span>
        <span
          v-if="candidatesCount > 0"
          class="text-[9px] px-1.5 py-0 rounded-full font-mono font-bold shrink-0"
          :class="activeTab === 'artwork' ? 'bg-primary/10 text-primary border border-primary/20' : 'bg-secondary text-secondary-foreground border border-border/50'"
        >
          {{ candidatesCount }}
        </span>
      </button>

      <!-- Tab 4: Production & Mockups -->
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'production'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'production'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'production')"
      >
        <Icon v-if="isProductionActive" name="lucide:loader-circle" class="size-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
        <Icon v-else-if="isProductionDone" name="lucide:circle-check" class="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        <Icon v-else name="lucide:file-image" class="size-3.5 shrink-0" :class="activeTab === 'production' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden 2xl:inline">3. Production &amp; Mockups</span>
        <span class="truncate 2xl:hidden">3. Production</span>
        <Badge
          v-if="isProductionDone"
          variant="success"
          class="text-[9px] px-1.5 py-0 font-bold uppercase tracking-wider shrink-0 hidden sm:inline-flex"
        >
          Ready
        </Badge>
      </button>

      <!-- Tab 5: Listing & IP Review -->
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'listing'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'listing'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'listing')"
      >
        <Icon v-if="isListingActive" name="lucide:loader-circle" class="size-3.5 shrink-0 animate-spin text-primary" aria-hidden="true" />
        <Icon v-else-if="isGate3Done" name="lucide:circle-check" class="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        <Icon v-else name="lucide:tags" class="size-3.5 shrink-0" :class="activeTab === 'listing' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden 2xl:inline">4. Listing &amp; IP Review</span>
        <span class="truncate 2xl:hidden">4. Listing &amp; IP Review</span>
        <Badge
          v-if="isGate3Done"
          variant="success"
          class="text-[9px] px-1.5 py-0 font-bold uppercase tracking-wider shrink-0 hidden sm:inline-flex"
        >
          Approved
        </Badge>
      </button>

      <!-- Tab 6: Etsy Draft -->
      <button
        v-if="isGate3Done"
        type="button"
        role="tab"
        :aria-selected="activeTab === 'etsy'"
        class="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:flex-1 lg:min-w-0"
        :class="
          activeTab === 'etsy'
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="emit('update:activeTab', 'etsy')"
      >
        <Icon v-if="workflowState === 'ETSY_DRAFT_CREATED'" name="lucide:circle-check" class="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        <Icon v-else name="lucide:store" class="size-3.5 shrink-0" :class="activeTab === 'etsy' ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span class="truncate hidden 2xl:inline">5. Etsy Draft</span>
        <span class="truncate 2xl:hidden">5. Etsy Draft</span>
        <Badge
          v-if="workflowState === 'ETSY_DRAFT_CREATED'"
          variant="success"
          class="text-[9px] px-1.5 py-0 font-bold uppercase tracking-wider shrink-0 hidden sm:inline-flex"
        >
          Drafted
        </Badge>
      </button>
    </div>
  </nav>
</template>
