<script setup lang="ts">
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Edit3,
  Star,
  ShieldAlert,
} from "lucide-vue-next";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import CardFooter from "~/components/ui/CardFooter.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

interface DesignPrompt {
  id: string;
  concept_id: string;
  version: number;
  positive_prompt: string;
  negative_prompt: string;
  typography_instructions: string | null;
  exact_slogan: string | null;
  intended_product_uses: string[];
  style_notes: string | null;
  palette: string | null;
  post_generation_checklist: string[];
  change_note: string | null;
  created_at: string;
}

interface Concept {
  id: string;
  workflow_id: string;
  original_idea_id: string | null;
  research_run_id: string | null;
  title: string;
  description: string;
  origin: string;
  differentiation: string;
  target_buyer: string | null;
  buyer_use_case: string | null;
  seasonality: string;
  risk_level: string;
  risk_note: string | null;
  score: number | null;
  score_breakdown: Record<string, number>;
  score_explanation: string | null;
  status: string;
  created_at: string;
  prompts: DesignPrompt[];
}

interface Workflow {
  id: string;
  state: string;
  version: number;
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

const props = defineProps<{
  workflow: Workflow;
  concepts: Concept[];
  latestRun: ResearchRun | null;
  approvedConcept?: Concept;
}>();

const emit = defineEmits<{
  (e: "startResearch"): void;
  (e: "decideGate", conceptId: string, decision: "APPROVED" | "REJECTED"): void;
  (e: "editPrompt", conceptId: string): void;
}>();
</script>

<template>
  <div class="space-y-6">
    <!-- State 1: Research in Progress -->
    <Card
      v-if="workflow.state === 'RESEARCH_QUEUED' || workflow.state === 'RESEARCHING'"
      class="p-8 text-center bg-indigo-50/40 border-indigo-100 shadow-2xs"
    >
      <RotateCw class="h-8 w-8 animate-spin text-indigo-600 mx-auto mb-3" />
      <h2 class="text-lg font-bold text-zinc-900 mb-1">AI Market Research in Progress</h2>
      <p class="text-xs text-zinc-500 max-w-md mx-auto">
        Our background worker is analyzing seasonal demand on Etsy, matching keyword query angles, screening trademarks, and drafting structured prompts. This will automatically refresh.
      </p>
    </Card>

    <!-- State 2: Research Failed -->
    <Card
      v-else-if="workflow.state === 'RESEARCH_FAILED'"
      class="p-8 text-center bg-rose-50/50 border-rose-200"
    >
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-100 text-rose-600 mb-3">
        <AlertCircle class="h-6 w-6" />
      </div>
      <h2 class="text-lg font-bold text-rose-900 mb-1">Research Campaign Failed</h2>
      <p class="text-xs text-rose-700 max-w-md mx-auto mb-4">
        Reason: {{ latestRun?.failure_reason || 'An unexpected worker error occurred.' }}
      </p>
      <Button variant="destructive" size="default" class="font-semibold" @click="emit('startResearch')">
        Retry Campaign Research
      </Button>
    </Card>

    <!-- State 3: Concepts Workspace -->
    <div v-else class="space-y-6">
      <!-- State Info / Guidance Alerts -->
      <Alert v-if="workflow.state === 'IDEA_REVIEW'" variant="info">
        <Sparkles class="h-4 w-4" />
        <div>
          <AlertTitle class="font-bold text-zinc-900">Choose one concept to continue.</AlertTitle>
          <AlertDescription class="text-xs text-zinc-600 mt-0.5">
            Review the AI-generated concepts below. Approve your preferred concept to proceed to Phase 6 Artwork Generation.
          </AlertDescription>
        </div>
      </Alert>

      <Alert v-if="workflow.state === 'IDEA_APPROVED'" variant="success">
        <CheckCircle2 class="h-4 w-4" />
        <div>
          <AlertTitle class="font-bold text-emerald-900">Concept Approved — Gate 1 Passed</AlertTitle>
          <AlertDescription class="text-xs text-emerald-700 mt-0.5">
            The selected concept is locked. Head to the <b>Artwork Studio</b> tab to generate and review candidate designs.
          </AlertDescription>
        </div>
      </Alert>

      <!-- Concepts Header -->
      <div class="flex items-center justify-between">
        <div class="space-y-0.5">
          <h2 class="text-xl font-bold tracking-tight text-zinc-900">Synthesised Product Concepts</h2>
          <p class="text-xs text-zinc-500">Ranked by commercial viability, competition gap, and trademark safety</p>
        </div>
        <Badge variant="secondary" class="text-xs font-mono font-bold">
          {{ concepts.length }} Options
        </Badge>
      </div>

      <Card v-if="concepts.length === 0" class="p-8 text-center">
        <p class="text-zinc-500 text-xs">No concepts generated for this workflow yet.</p>
      </Card>

      <!-- Concept Cards List -->
      <div v-else class="space-y-6">
        <Card
          v-for="concept in concepts"
          :key="concept.id"
          class="shadow-2xs transition-all"
          :class="[
            concept.status?.toUpperCase() === 'APPROVED'
              ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/10'
              : concept.status?.toUpperCase() === 'REJECTED'
                ? 'border-rose-200 opacity-60 bg-rose-50/10'
                : 'border-zinc-200',
            approvedConcept && concept.status?.toUpperCase() !== 'APPROVED' ? 'opacity-40 pointer-events-none' : '',
          ]"
        >
          <CardHeader class="pb-3 border-b border-zinc-100 bg-zinc-50/30">
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <CardTitle class="text-lg font-bold">{{ concept.title }}</CardTitle>
                  <Badge v-if="concept.status?.toUpperCase() === 'APPROVED'" variant="success" class="text-[10px] px-2 py-0 font-bold">
                    Selected Concept
                  </Badge>
                  <Badge v-if="concept.status?.toUpperCase() === 'REJECTED'" variant="destructive" class="text-[10px] px-2 py-0">
                    Rejected
                  </Badge>
                </div>
                <p class="text-xs text-zinc-400">Origin: {{ concept.origin }}</p>
              </div>

              <Badge variant="outline" class="gap-1 font-bold text-xs bg-indigo-50 text-indigo-700 border-indigo-200 px-2.5 py-1">
                <Star class="h-3 w-3 fill-indigo-600 text-indigo-600" />
                <span>{{ concept.score ? concept.score.toFixed(2) : 'N/A' }} / 5.0</span>
              </Badge>
            </div>
          </CardHeader>

          <CardContent class="p-5 space-y-4 text-xs text-zinc-600">
            <p class="text-sm text-zinc-700 leading-relaxed">{{ concept.description }}</p>

            <!-- Differentiation Strategy -->
            <div class="rounded-lg bg-zinc-50 p-3 border border-zinc-100">
              <span class="font-bold text-zinc-800 block mb-0.5 text-[11px]">Market Differentiation Strategy:</span>
              <p class="text-zinc-600">{{ concept.differentiation }}</p>
            </div>

            <!-- Risk Alert -->
            <div
              v-if="concept.risk_level && concept.risk_level !== 'low'"
              class="rounded-lg bg-rose-50 p-3 border border-rose-200 text-rose-900"
            >
              <div class="flex items-center gap-1.5 font-bold text-[11px]">
                <ShieldAlert class="h-3.5 w-3.5 text-rose-600" />
                <span>IP Risk Level: {{ concept.risk_level.toUpperCase() }}</span>
              </div>
              <p class="mt-0.5 text-rose-700 text-[11px]">{{ concept.risk_note }}</p>
            </div>

            <!-- Score Breakdown -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-zinc-100">
              <div v-for="(val, key) in concept.score_breakdown" :key="key" class="bg-zinc-50 p-2 rounded border border-zinc-100">
                <span class="text-zinc-400 uppercase tracking-wider block text-[10px]">{{ key.replace('_', ' ') }}</span>
                <span class="text-zinc-900 font-bold text-xs">{{ val }} / 5</span>
              </div>
            </div>

            <!-- Active Design Prompt -->
            <div class="rounded-xl bg-indigo-50/30 p-3.5 border border-indigo-100 space-y-2">
              <div class="flex items-center justify-between border-b border-indigo-100 pb-1.5">
                <span class="font-bold text-indigo-900 text-xs">
                  Active Design Prompt (v{{ concept.prompts[concept.prompts.length - 1]?.version || 1 }})
                </span>
                <Button
                  v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
                  variant="ghost"
                  size="sm"
                  class="h-6 px-2 text-xs font-bold text-indigo-700 hover:text-indigo-800"
                  @click="emit('editPrompt', concept.id)"
                >
                  <Edit3 class="h-3 w-3 mr-1" />
                  <span>Edit Prompt</span>
                </Button>
              </div>

              <div class="space-y-1 font-mono text-[11px]">
                <p><span class="font-bold text-zinc-500">Positive:</span> {{ concept.prompts[concept.prompts.length - 1]?.positive_prompt }}</p>
                <p><span class="font-bold text-zinc-500">Negative:</span> {{ concept.prompts[concept.prompts.length - 1]?.negative_prompt }}</p>
                <p v-if="concept.prompts[concept.prompts.length - 1]?.exact_slogan">
                  <span class="font-bold text-zinc-500">Typography:</span>
                  "{{ concept.prompts[concept.prompts.length - 1]?.exact_slogan }}"
                </p>
              </div>
            </div>
          </CardContent>

          <!-- Gate 1 Actions -->
          <CardFooter
            v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
            class="flex justify-end gap-3 border-t border-zinc-100 pt-4 bg-zinc-50/50"
          >
            <Button
              variant="outline"
              size="sm"
              class="text-rose-700 hover:bg-rose-50 hover:border-rose-200"
              @click="emit('decideGate', concept.id, 'REJECTED')"
            >
              Reject Concept
            </Button>
            <Button
              variant="success"
              size="sm"
              class="font-bold"
              @click="emit('decideGate', concept.id, 'APPROVED')"
            >
              Approve This Concept
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  </div>
</template>
