<script setup lang="ts">
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import { isStopped } from "~/composables/useWorkflowControls";
import { getProductIcon } from "~/config/icons";

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

function formatProductLabel(product: string): string {
  const norm = product.toLowerCase().replace(/[- ]/g, "_");
  if (norm.includes("mug") || norm.includes("cup")) return "Ceramic Mug";
  if (norm.includes("sweatshirt") || norm.includes("hoodie")) return "Sweatshirt";
  if (norm.includes("tshirt") || norm.includes("t_shirt") || norm.includes("shirt")) return "T-Shirt";
  if (norm.includes("tote") || norm.includes("bag")) return "Tote Bag";
  return product.charAt(0).toUpperCase() + product.slice(1);
}
</script>

<template>
  <div class="space-y-6">
    <!-- Paused Banner if stopped -->
    <Card v-if="isStopped(workflow.state)" class="p-8 text-center bg-zinc-50 border-dashed">
      <h2 class="text-lg font-bold text-zinc-900 mb-1">Campaign paused</h2>
      <p class="text-xs text-zinc-500 max-w-md mx-auto mb-4">
        Nothing is currently running. All generated concepts, prompts, and artwork candidates are preserved. Click Resume to continue without wasting tokens.
      </p>
      <div class="flex items-center justify-center gap-3 flex-wrap">
        <Button
          variant="default"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 font-semibold shadow-2xs bg-indigo-600 hover:bg-indigo-700 cursor-pointer"
          @click="emit('control', 'rerun')"
        >
          <Icon name="lucide:rotate-cw" class="size-3.5" aria-hidden="true" />
          <span>Resume from Current Step</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 text-xs text-zinc-600 border-zinc-200 bg-white hover:bg-zinc-100 cursor-pointer"
          @click="emit('control', 'rerun', { fromScratch: true })"
        >
          <span>Restart from Brief (New Research)</span>
        </Button>
      </div>
    </Card>

    <!-- Quick Navigation Banner / Pipeline Jump Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div
        class="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs hover:border-indigo-300 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'concepts')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-zinc-500 uppercase tracking-wider">Phase 1–5</span>
          <Icon name="lucide:sparkles" class="size-4 text-indigo-600" aria-hidden="true" />
        </div>
        <h3 class="text-sm font-bold text-zinc-900">Market Concepts & Research</h3>
        <p class="text-xs text-zinc-500">Review AI idea analysis, scoring, IP risk checks, and prompt versions.</p>
        <div class="pt-2 flex items-center text-xs font-bold text-indigo-600 gap-1">
          <span>Open Concepts</span>
          <Icon name="lucide:arrow-right" class="size-3.5" aria-hidden="true" />
        </div>
      </div>

      <div
        class="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs hover:border-indigo-300 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'artwork')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-zinc-500 uppercase tracking-wider">Phase 6</span>
          <Icon name="lucide:image" class="size-4 text-indigo-600" aria-hidden="true" />
        </div>
        <h3 class="text-sm font-bold text-zinc-900">Artwork Studio & Review</h3>
        <p class="text-xs text-zinc-500">Configure Recraft/Gemini generators, review candidate designs, and refine.</p>
        <div class="pt-2 flex items-center text-xs font-bold text-indigo-600 gap-1">
          <span>Open Artwork Studio</span>
          <Icon name="lucide:arrow-right" class="size-3.5" aria-hidden="true" />
        </div>
      </div>

      <div
        class="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs hover:border-indigo-300 hover:shadow-xs transition-all cursor-pointer space-y-2"
        @click="emit('navigate', 'production')"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-zinc-500 uppercase tracking-wider">Phase 7</span>
          <Icon name="lucide:file-image" class="size-4 text-indigo-600" aria-hidden="true" />
        </div>
        <h3 class="text-sm font-bold text-zinc-900">PNG Master & Mockups</h3>
        <p class="text-xs text-zinc-500">Deterministic 4500×5400 px master print PNG, QA validation, and realistic mockups.</p>
        <div class="pt-2 flex items-center text-xs font-bold text-indigo-600 gap-1">
          <span>Open Production Gallery</span>
          <Icon name="lucide:arrow-right" class="size-3.5" aria-hidden="true" />
        </div>
      </div>
    </div>

    <!-- Main Brief Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Target Brief Card -->
      <Card class="shadow-2xs">
        <CardHeader class="pb-3 border-b border-zinc-100 bg-zinc-50/50">
          <div class="flex items-center gap-2">
            <Icon name="lucide:target" class="size-4 text-indigo-600" aria-hidden="true" />
            <CardTitle class="text-base font-bold">Campaign Target Specifications</CardTitle>
          </div>
          <CardDescription class="text-xs text-zinc-500">
            Marketplace target, localization parameters, and intended merchandise types.
          </CardDescription>
        </CardHeader>
        <CardContent class="p-5 space-y-4 text-xs">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <span class="text-zinc-400 block uppercase tracking-wider text-[10px] font-semibold">Target Marketplace</span>
              <span class="text-zinc-900 font-bold uppercase">{{ workflow.target_marketplace }}</span>
            </div>
            <div>
              <span class="text-zinc-400 block uppercase tracking-wider text-[10px] font-semibold">Country & Language</span>
              <span class="text-zinc-900 font-bold uppercase">{{ workflow.target_country }} ({{ workflow.output_language }})</span>
            </div>
          </div>

          <div>
            <span class="text-zinc-400 block uppercase tracking-wider text-[10px] font-semibold">Target Buyer Audience</span>
            <span class="text-zinc-900 font-medium">{{ workflow.target_buyer || 'Broad Consumer Market' }}</span>
          </div>

          <div>
            <span class="text-zinc-400 block uppercase tracking-wider text-[10px] font-semibold mb-1.5">Intended Physical Products</span>
            <div class="flex flex-wrap gap-1.5">
              <Badge v-for="use in workflow.intended_product_uses" :key="use" variant="secondary" class="text-[11px] px-2.5 py-1 inline-flex items-center gap-1.5">
                <Icon :name="getProductIcon(use)" class="size-3.5 text-zinc-500" aria-hidden="true" />
                <span>{{ formatProductLabel(use) }}</span>
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Original User Brief Card -->
      <Card v-if="originalIdea" class="shadow-2xs bg-indigo-50/20 border-indigo-100">
        <CardHeader class="pb-3 border-b border-indigo-100/60 bg-indigo-50/40">
          <div class="flex items-center gap-2">
            <Icon name="lucide:lightbulb" class="size-4 text-indigo-600" aria-hidden="true" />
            <CardTitle class="text-base font-bold">
              Original {{ workflow.idea_mode === 'hybrid' ? 'Theme / Direction Brief' : 'Idea Brief' }}
            </CardTitle>
          </div>
          <CardDescription class="text-xs text-indigo-900/70">
            Initial creator input used by AI market research to generate refined concepts.
          </CardDescription>
        </CardHeader>
        <CardContent class="p-5 space-y-4 text-xs text-zinc-700">
          <div>
            <span class="font-semibold text-zinc-500 block mb-1">Verbatim Wording:</span>
            <blockquote class="italic bg-white p-3 rounded-lg border border-zinc-200/80 text-zinc-800">
              "{{ originalIdea.original_text }}"
            </blockquote>
          </div>

          <div class="grid grid-cols-2 gap-3 text-xs">
            <div v-if="originalIdea.slogan">
              <span class="font-semibold text-zinc-500 block text-[10px]">Exact Slogan:</span>
              <span class="font-mono bg-white px-1.5 py-0.5 rounded border border-zinc-200 text-zinc-900 inline-block mt-0.5">{{ originalIdea.slogan }}</span>
            </div>
            <div v-if="originalIdea.desired_style">
              <span class="font-semibold text-zinc-500 block text-[10px]">Desired Style:</span>
              <span class="text-zinc-900">{{ originalIdea.desired_style }}</span>
            </div>
            <div v-if="originalIdea.occasion">
              <span class="font-semibold text-zinc-500 block text-[10px]">Occasion:</span>
              <span class="text-zinc-900">{{ originalIdea.occasion }}</span>
            </div>
            <div v-if="originalIdea.season">
              <span class="font-semibold text-zinc-500 block text-[10px]">Season:</span>
              <span class="text-zinc-900">{{ originalIdea.season }}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
