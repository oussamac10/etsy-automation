<script setup lang="ts">
import { computed } from "vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import { isStopped } from "~/composables/useWorkflowControls";
import { getProductIcon } from "~/config/icons";
import { getProductLabel, normalizeProductKey } from "~/utils/mockupProducts";

interface Workflow {
  id: string;
  name: string;
  idea_mode: string;
  target_marketplace: string;
  target_country: string;
  output_language: string;
  target_buyer: string | null;
  intended_product_uses: string[];
  state: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface OriginalIdea {
  id: string;
  original_text: string;
  slogan: string | null;
  desired_style: string | null;
  audience: string | null;
  occasion: string | null;
  season: string | null;
  product_uses: string[];
}

interface ResearchRun {
  id: string;
  status: string;
  confidence: string | null;
  proposed_test: string | null;
  started_at: string | null;
  completed_at: string | null;
  failure_reason: string | null;
}

interface ProductionJob {
  id: string;
  status: string;
  mockup_assets?: Array<{
    provenance?: {
      product_type?: string;
      asset_type?: string;
      source?: string;
    };
  }>;
}

const props = defineProps<{
  workflow: Workflow;
  originalIdea: OriginalIdea | null;
  latestRun: ResearchRun | null;
  latestProductionJob: ProductionJob | null;
  pendingWorkflowId: string | null;
}>();

const emit = defineEmits<{
  (e: "control", action: string, options?: Record<string, unknown>): void;
  (e: "navigate", tab: string): void;
}>();

const displayProductUses = computed<string[]>(() => {
  const seen = new Set<string>();
  const list: string[] = [];

  // 1. From workflow.intended_product_uses
  for (const p of props.workflow?.intended_product_uses || []) {
    const k = normalizeProductKey(p);
    if (k && !seen.has(k)) {
      seen.add(k);
      list.push(k);
    }
  }

  // 2. From active mockup assets in latest production job
  for (const m of props.latestProductionJob?.mockup_assets || []) {
    const pt = m.provenance?.product_type;
    if (pt) {
      const k = normalizeProductKey(pt);
      if (k && !seen.has(k)) {
        seen.add(k);
        list.push(k);
      }
    }
  }

  // 3. From originalIdea.product_uses
  for (const p of props.originalIdea?.product_uses || []) {
    const k = normalizeProductKey(p);
    if (k && !seen.has(k)) {
      seen.add(k);
      list.push(k);
    }
  }

  return list;
});
</script>

<template>
  <div class="space-y-6">
    <!-- Paused Banner if stopped -->
    <Card v-if="isStopped(workflow.state)" class="p-8 text-center bg-secondary/40 border-dashed border-border">
      <h2 class="text-lg font-bold text-foreground mb-1">Campaign paused</h2>
      <p class="text-xs text-muted-foreground max-w-md mx-auto mb-4">
        Nothing is currently running. All generated concepts, prompts, and artwork candidates are preserved. Click Resume to continue without wasting tokens.
      </p>
      <div class="flex items-center justify-center gap-3 flex-wrap">
        <Button
          variant="default"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 font-semibold shadow-2xs cursor-pointer"
          @click="emit('control', 'rerun')"
        >
          <Icon name="lucide:rotate-cw" class="size-3.5" aria-hidden="true" />
          <span>Resume from Current Step</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 text-xs text-secondary-foreground border-border bg-white hover:bg-secondary hover:text-foreground cursor-pointer"
          @click="emit('control', 'rerun', { fromScratch: true })"
        >
          <span>Restart from Brief (New Research)</span>
        </Button>
      </div>
    </Card>

    <!-- Quick Navigation Banner / Pipeline Jump Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div
        class="rounded-xl border border-border bg-card p-4 shadow-2xs hover:border-primary/50 hover:bg-secondary/30 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'concepts')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-foreground uppercase tracking-wider">Step 1</span>
          <Icon name="lucide:arrow-right" class="size-4 text-muted-foreground" aria-hidden="true" />
        </div>
        <p class="text-sm font-semibold text-foreground">Market Research & Concept</p>
        <p class="text-xs text-muted-foreground line-clamp-2">
          Discover keyword demand, competitor gaps, and review AI scoring and trademark screening.
        </p>
      </div>

      <div
        class="rounded-xl border border-border bg-card p-4 shadow-2xs hover:border-primary/50 hover:bg-secondary/30 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'artwork')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-foreground uppercase tracking-wider">Step 2</span>
          <Icon name="lucide:arrow-right" class="size-4 text-muted-foreground" aria-hidden="true" />
        </div>
        <p class="text-sm font-semibold text-foreground">Artwork Studio</p>
        <p class="text-xs text-muted-foreground line-clamp-2">
          Generate high-resolution transparent graphics, refine prompts, and approve candidates.
        </p>
      </div>

      <div
        class="rounded-xl border border-border bg-card p-4 shadow-2xs hover:border-primary/50 hover:bg-secondary/30 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'production')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-foreground uppercase tracking-wider">Step 3</span>
          <Icon name="lucide:arrow-right" class="size-4 text-muted-foreground" aria-hidden="true" />
        </div>
        <p class="text-sm font-semibold text-foreground">Production & Mockups</p>
        <p class="text-xs text-muted-foreground line-clamp-2">
          300 DPI master print file, automated QA checks, and multi-product mockup gallery.
        </p>
      </div>
    </div>

    <!-- Overview Details Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Campaign Parameters Card -->
      <Card class="shadow-2xs">
        <CardHeader class="pb-3 border-b border-border">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Icon name="lucide:sliders" class="size-4 text-primary" aria-hidden="true" />
              <CardTitle class="text-base font-bold">Campaign Parameters</CardTitle>
            </div>
            <Badge variant="outline" class="text-[10px] uppercase font-bold tracking-wider">
              {{ workflow.idea_mode }}
            </Badge>
          </div>
          <CardDescription class="text-xs">
            Baseline configuration for research, copy generation, and marketplace targeting.
          </CardDescription>
        </CardHeader>
        <CardContent class="p-5 space-y-4 text-xs">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <span class="text-muted-foreground block uppercase tracking-wider text-[10px] font-semibold">Marketplace</span>
              <span class="text-foreground font-medium uppercase">{{ workflow.target_marketplace }} ({{ workflow.target_country }})</span>
            </div>
            <div>
              <span class="text-muted-foreground block uppercase tracking-wider text-[10px] font-semibold">Language</span>
              <span class="text-foreground font-medium uppercase">{{ workflow.output_language }}</span>
            </div>
          </div>

          <div>
            <span class="text-muted-foreground block uppercase tracking-wider text-[10px] font-semibold">Target Buyer Audience</span>
            <span class="text-foreground font-medium">{{ workflow.target_buyer || 'Broad Consumer Market' }}</span>
          </div>

          <div>
            <span class="text-muted-foreground block uppercase tracking-wider text-[10px] font-semibold mb-1.5">Intended Physical Products</span>
            <div v-if="displayProductUses.length > 0" class="flex flex-wrap gap-1.5">
              <Badge v-for="use in displayProductUses" :key="use" variant="secondary" class="text-[11px] px-2.5 py-1 inline-flex items-center gap-1.5 shadow-2xs">
                <Icon :name="getProductIcon(use)" class="size-3.5 text-muted-foreground" aria-hidden="true" />
                <span>{{ getProductLabel(use) }}</span>
              </Badge>
            </div>
            <p v-else class="text-xs text-muted-foreground italic">
              No products selected yet. Select categories in the Production & Mockups tab.
            </p>
          </div>
        </CardContent>
      </Card>

      <!-- Original User Brief Card -->
      <Card v-if="originalIdea" class="shadow-2xs bg-secondary/30 border-border">
        <CardHeader class="pb-3 border-b border-border bg-secondary/50">
          <div class="flex items-center gap-2">
            <Icon name="lucide:lightbulb" class="size-4 text-primary" aria-hidden="true" />
            <CardTitle class="text-base font-bold">
              Original {{ workflow.idea_mode === 'hybrid' ? 'Theme / Direction Brief' : 'Idea Brief' }}
            </CardTitle>
          </div>
          <CardDescription class="text-xs text-secondary-foreground">
            Initial creator input used by AI market research to generate refined concepts.
          </CardDescription>
        </CardHeader>
        <CardContent class="p-5 space-y-4 text-xs text-secondary-foreground">
          <div>
            <span class="font-semibold text-secondary-foreground block mb-1">Verbatim Wording:</span>
            <blockquote class="italic bg-white p-3 rounded-lg border border-border text-foreground">
              "{{ originalIdea.original_text }}"
            </blockquote>
          </div>

          <div class="grid grid-cols-2 gap-3 text-xs">
            <div v-if="originalIdea.slogan">
              <span class="font-semibold text-secondary-foreground block text-[10px]">Exact Slogan:</span>
              <span class="font-mono bg-white px-1.5 py-0.5 rounded border border-border text-foreground inline-block mt-0.5">{{ originalIdea.slogan }}</span>
            </div>
            <div v-if="originalIdea.desired_style">
              <span class="font-semibold text-secondary-foreground block text-[10px]">Desired Style:</span>
              <span class="text-foreground font-medium">{{ originalIdea.desired_style }}</span>
            </div>
            <div v-if="originalIdea.occasion">
              <span class="font-semibold text-secondary-foreground block text-[10px]">Occasion:</span>
              <span class="text-foreground font-medium">{{ originalIdea.occasion }}</span>
            </div>
            <div v-if="originalIdea.season">
              <span class="font-semibold text-secondary-foreground block text-[10px]">Season:</span>
              <span class="text-foreground font-medium">{{ originalIdea.season }}</span>
            </div>

            <!-- Target Product Categories in Brief -->
            <div v-if="displayProductUses.length > 0" class="col-span-2 pt-1 border-t border-border/70">
              <span class="font-semibold text-secondary-foreground block text-[10px] mb-1.5">Intended Products:</span>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="use in displayProductUses"
                  :key="use"
                  class="text-[10px] font-medium px-2 py-0.5 rounded-md bg-white border border-border text-foreground inline-flex items-center gap-1 shadow-2xs"
                >
                  <Icon :name="getProductIcon(use)" class="size-3 text-muted-foreground" aria-hidden="true" />
                  <span>{{ getProductLabel(use) }}</span>
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
