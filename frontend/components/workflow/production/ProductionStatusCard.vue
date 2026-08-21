<script setup lang="ts">
import type { ProductionJob } from "~/types/production";
import Button from "~/components/ui/Button.vue";

defineProps<{
  state: string;
  latestProductionJob: ProductionJob | null;
  isProductionLoading: boolean;
  exactSlogan?: string | null;
}>();

const emit = defineEmits<{
  (e: "startProduction"): void;
}>();
</script>

<template>
  <div>
    <!-- Ready to Produce State (Artwork Approved) -->
    <div v-if="!latestProductionJob && (state === 'ARTWORK_APPROVED' || state === 'IDEA_APPROVED')" class="space-y-4">
      <div class="rounded-xl border border-border bg-secondary/40 p-5 space-y-4">
        <div class="flex items-start gap-3">
          <div class="h-9 w-9 rounded-lg bg-secondary border border-border flex items-center justify-center text-primary shrink-0">
            <Icon name="lucide:sparkles" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-1">
            <h4 class="text-sm font-bold text-foreground">Artwork Approved & Ready for Master PNG Processing</h4>
            <p class="text-xs text-secondary-foreground leading-relaxed">
              Start print-ready master PNG production. The pipeline applies safe-margin trimming, 4500×5400 px @ 300 DPI upscale, slogan typography overlay, and strict transparency QA. Once complete, you can composite multiple mockups.
            </p>
          </div>
        </div>

        <div v-if="exactSlogan" class="rounded-lg bg-white border border-border p-3 text-xs flex items-center justify-between">
          <span class="text-muted-foreground font-medium">Approved Slogan:</span>
          <span class="font-bold text-foreground font-mono">"{{ exactSlogan }}"</span>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <Button
            variant="default"
            size="sm"
            class="font-bold gap-2 shadow-xs cursor-pointer inline-flex items-center"
            :disabled="isProductionLoading"
            @click="emit('startProduction')"
          >
            <Icon name="lucide:play" class="size-4" aria-hidden="true" />
            <span>Start PNG Production</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Running State -->
    <div
      v-else-if="latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED' || (state === 'PRODUCTION' && latestProductionJob?.status !== 'SUCCEEDED')"
      class="py-12 text-center space-y-4"
    >
      <div class="h-12 w-12 rounded-full bg-secondary border border-border flex items-center justify-center mx-auto text-primary shadow-xs">
        <Icon name="lucide:loader-circle" class="size-6 animate-spin" aria-hidden="true" />
      </div>
      <div class="space-y-1">
        <h4 class="text-base font-bold text-foreground">Processing Master PNG & Quality Checks</h4>
        <p class="text-xs text-muted-foreground max-w-md mx-auto">
          Preparing print files: safe trim margin, 4500×5400 px upscale @ 300 DPI, transparency verification, and slogan typography integration.
        </p>
      </div>
    </div>

    <!-- Artwork Selection Required State (Artwork not selected yet) -->
    <div v-else-if="!latestProductionJob" class="space-y-4">
      <div
        class="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
        data-testid="gate-2-pending-warning"
      >
        <div class="space-y-1 min-w-0">
          <p class="font-semibold flex items-center gap-2 text-foreground text-sm">
            <Icon name="lucide:image" class="size-4 shrink-0 text-amber-500" aria-hidden="true" />
            <span>Artwork Selection Required</span>
          </p>
          <p class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed">
            PNG production requires an approved master artwork design. Please visit <b>Step 2 (Artwork Studio)</b> to generate, refine, and approve your design before generating the print-ready PNG and product mockups.
          </p>
        </div>
        <NuxtLink :to="{ query: { tab: 'artwork' } }" class="shrink-0 self-start sm:self-auto">
          <Button variant="outline" size="sm" class="gap-1.5 font-semibold bg-background text-foreground border-border hover:bg-muted cursor-pointer">
            <Icon name="lucide:arrow-left" class="size-3.5" aria-hidden="true" />
            <span>Go to Artwork Studio</span>
          </Button>
        </NuxtLink>
      </div>
    </div>
  </div>
</template>
