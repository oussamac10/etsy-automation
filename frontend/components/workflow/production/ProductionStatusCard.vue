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
    <!-- Ready to Produce State (Gate 2 Approved) -->
    <div v-if="!latestProductionJob && (state === 'ARTWORK_APPROVED' || state === 'IDEA_APPROVED')" class="space-y-4">
      <div class="rounded-xl border border-border bg-secondary/40 p-5 space-y-4">
        <div class="flex items-start gap-3">
          <div class="h-9 w-9 rounded-lg bg-secondary border border-border flex items-center justify-center text-primary shrink-0">
            <Icon name="lucide:sparkles" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-1">
            <h4 class="text-sm font-bold text-foreground">Artwork Approved & Ready for Master PNG Processing</h4>
            <p class="text-xs text-secondary-foreground leading-relaxed">
              Start deterministic Phase 7 master PNG production. The pipeline applies 8% safe-margin trimming, 4500×5400 px @ 300 DPI upscale, slogan typography overlay, and strict transparency QA. Once complete, you can composite multiple mockups.
            </p>
          </div>
        </div>

        <div v-if="exactSlogan" class="rounded-lg bg-white border border-border p-3 text-xs flex items-center justify-between">
          <span class="text-muted-foreground font-medium">Recorded Gate 1 Slogan:</span>
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
        <Icon name="lucide:loader-2" class="size-6 animate-spin" aria-hidden="true" />
      </div>
      <div class="space-y-1">
        <h4 class="text-base font-bold text-foreground">Processing Master PNG & Quality Checks</h4>
        <p class="text-xs text-muted-foreground max-w-md mx-auto">
          Running Sharp image pipeline: safe trim margin (8%), 4500×5400 px upscale @ 300 DPI, transparency verification, and slogan typography integration.
        </p>
      </div>
    </div>
  </div>
</template>
