<script setup lang="ts">
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
      class="p-8 text-center bg-secondary/40 border-border shadow-2xs"
    >
      <Icon name="lucide:loader-circle" class="size-8 animate-spin text-primary mx-auto mb-3" aria-hidden="true" />
      <h2 class="text-lg font-bold text-foreground mb-1">AI Market Research in Progress</h2>
      <p class="text-xs text-muted-foreground max-w-md mx-auto">
        Our background worker is analyzing seasonal marketplace demand, matching keyword query angles, screening trademarks, and drafting structured prompts. This will automatically refresh.
      </p>
    </Card>

    <!-- State 2: Research Failed -->
    <Card
      v-else-if="workflow.state === 'RESEARCH_FAILED'"
      class="p-8 text-center bg-red-50/60 border-red-200"
    >
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-destructive mb-3">
        <Icon name="lucide:circle-alert" class="size-6" aria-hidden="true" />
      </div>
      <h2 class="text-lg font-bold text-destructive mb-1">Research Campaign Failed</h2>
      <p class="text-xs text-red-700 max-w-md mx-auto mb-4">
        Reason: {{ latestRun?.failure_reason || 'An unexpected worker error occurred.' }}
      </p>
      <Button variant="destructive" size="default" class="font-semibold cursor-pointer" @click="emit('startResearch')">
        <Icon name="lucide:rotate-ccw" class="size-4 mr-1.5" aria-hidden="true" />
        <span>Retry Campaign Research</span>
      </Button>
    </Card>

    <!-- State 3: Concepts Workspace -->
    <div v-else class="space-y-6">
      <!-- State Info / Guidance Alerts -->
      <Alert v-if="workflow.state === 'IDEA_REVIEW'" variant="info">
        <Icon name="lucide:sparkles" class="size-4 text-primary" aria-hidden="true" />
        <div>
          <AlertTitle class="font-bold text-foreground">Choose one concept to continue.</AlertTitle>
          <AlertDescription class="text-xs text-secondary-foreground mt-0.5">
            Review the AI-generated concepts below. Approve your preferred concept to proceed to Phase 6 Artwork Generation.
          </AlertDescription>
        </div>
      </Alert>

      <Alert v-if="workflow.state === 'IDEA_APPROVED'" variant="success">
        <Icon name="lucide:circle-check" class="size-4 text-emerald-600" aria-hidden="true" />
        <div>
          <AlertTitle class="font-bold text-emerald-800">Concept Approved — Gate 1 Passed</AlertTitle>
          <AlertDescription class="text-xs text-emerald-700 mt-0.5">
            The selected concept is locked. Head to the <b>Artwork Studio</b> tab to generate and review candidate designs.
          </AlertDescription>
        </div>
      </Alert>

      <!-- Concepts Header -->
      <div class="flex items-center justify-between">
        <div class="space-y-0.5">
          <h2 class="text-xl font-bold tracking-tight text-foreground">Synthesised Product Concepts</h2>
          <p class="text-xs text-muted-foreground">Ranked by commercial viability, competition gap, and trademark safety</p>
        </div>
        <Badge variant="secondary" class="text-xs font-mono font-bold">
          {{ concepts.length }} Options
        </Badge>
      </div>

      <Card v-if="concepts.length === 0" class="p-8 text-center">
        <p class="text-muted-foreground text-xs">No concepts generated for this workflow yet.</p>
      </Card>

      <!-- Concept Cards List -->
      <div v-else class="space-y-6">
        <Card
          v-for="concept in concepts"
          :key="concept.id"
          class="shadow-2xs transition-all"
          :class="[
            concept.status?.toUpperCase() === 'APPROVED'
              ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/20'
              : concept.status?.toUpperCase() === 'REJECTED'
                ? 'border-red-200 opacity-60 bg-red-50/20'
                : 'border-border',
            approvedConcept && concept.status?.toUpperCase() !== 'APPROVED' ? 'opacity-40 pointer-events-none' : '',
          ]"
        >
          <CardHeader class="pb-3 border-b border-border bg-secondary/30">
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <CardTitle class="text-lg font-bold">{{ concept.title }}</CardTitle>
                  <Badge v-if="concept.status?.toUpperCase() === 'APPROVED'" variant="success" class="text-[10px] px-2 py-0 font-bold inline-flex items-center gap-1">
                    <Icon name="lucide:circle-check" class="size-3 text-emerald-600" aria-hidden="true" />
                    <span>Selected Concept</span>
                  </Badge>
                  <Badge v-if="concept.status?.toUpperCase() === 'REJECTED'" variant="destructive" class="text-[10px] px-2 py-0 inline-flex items-center gap-1">
                    <Icon name="lucide:circle-x" class="size-3 text-destructive" aria-hidden="true" />
                    <span>Rejected</span>
                  </Badge>
                </div>
                <p class="text-xs text-muted-foreground">Origin: {{ concept.origin }}</p>
              </div>

              <Badge variant="outline" class="gap-1 font-bold text-xs bg-secondary text-primary border border-border px-2.5 py-1 inline-flex items-center">
                <Icon name="lucide:gauge" class="size-3 text-primary" aria-hidden="true" />
                <span>{{ concept.score ? concept.score.toFixed(2) : 'N/A' }} / 5.0</span>
              </Badge>
            </div>
          </CardHeader>

          <CardContent class="p-5 space-y-4 text-xs text-secondary-foreground">
            <p class="text-sm text-foreground leading-relaxed">{{ concept.description }}</p>

            <!-- Differentiation Strategy -->
            <div class="rounded-lg bg-secondary/50 p-3 border border-border">
              <span class="font-bold text-foreground block mb-0.5 text-[11px]">Market Differentiation Strategy:</span>
              <p class="text-secondary-foreground">{{ concept.differentiation }}</p>
            </div>

            <!-- Risk Alert -->
            <div
              v-if="concept.risk_level && concept.risk_level !== 'low'"
              class="rounded-lg bg-red-50 p-3 border border-red-200 text-destructive"
            >
              <div class="flex items-center gap-1.5 font-bold text-[11px]">
                <Icon name="lucide:shield-alert" class="size-3.5 text-destructive" aria-hidden="true" />
                <span>IP Risk Level: {{ concept.risk_level.toUpperCase() }}</span>
              </div>
              <p class="mt-0.5 text-red-700 text-[11px]">{{ concept.risk_note }}</p>
            </div>

            <!-- Score Breakdown -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-border">
              <div v-for="(val, key) in concept.score_breakdown" :key="key" class="bg-secondary/40 p-2 rounded border border-border">
                <span class="text-muted-foreground uppercase tracking-wider block text-[10px]">{{ key.replace('_', ' ') }}</span>
                <span class="text-foreground font-bold text-xs">{{ val }} / 5</span>
              </div>
            </div>

            <!-- Active Design Prompt -->
            <div class="rounded-xl bg-secondary/30 p-3.5 border border-border space-y-2">
              <div class="flex items-center justify-between border-b border-border pb-1.5">
                <span class="font-bold text-foreground text-xs">
                  Active Design Prompt (v{{ concept.prompts[concept.prompts.length - 1]?.version || 1 }})
                </span>
                <Button
                  v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
                  variant="ghost"
                  size="sm"
                  class="h-6 px-2 text-xs font-bold text-primary hover:text-primary-hover hover:bg-secondary cursor-pointer inline-flex items-center gap-1"
                  @click="emit('editPrompt', concept.id)"
                >
                  <Icon name="lucide:pencil" class="size-3" aria-hidden="true" />
                  <span>Edit Prompt</span>
                </Button>
              </div>

              <div class="space-y-1 font-mono text-[11px]">
                <p><span class="font-bold text-muted-foreground">Positive:</span> {{ concept.prompts[concept.prompts.length - 1]?.positive_prompt }}</p>
                <p><span class="font-bold text-muted-foreground">Negative:</span> {{ concept.prompts[concept.prompts.length - 1]?.negative_prompt }}</p>
                <p v-if="concept.prompts[concept.prompts.length - 1]?.exact_slogan">
                  <span class="font-bold text-muted-foreground">Typography:</span>
                  "{{ concept.prompts[concept.prompts.length - 1]?.exact_slogan }}"
                </p>
              </div>
            </div>
          </CardContent>

          <!-- Gate 1 Actions -->
          <CardFooter
            v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
            class="flex justify-end gap-3 border-t border-border pt-4 bg-secondary/20"
          >
            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:bg-red-50 hover:border-red-200 cursor-pointer inline-flex items-center gap-1.5"
              @click="emit('decideGate', concept.id, 'REJECTED')"
            >
              <Icon name="lucide:circle-x" class="size-3.5" aria-hidden="true" />
              <span>Reject Concept</span>
            </Button>
            <Button
              variant="success"
              size="sm"
              class="font-bold cursor-pointer inline-flex items-center gap-1.5"
              @click="emit('decideGate', concept.id, 'APPROVED')"
            >
              <Icon name="lucide:circle-check" class="size-3.5" aria-hidden="true" />
              <span>Approve This Concept</span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  </div>
</template>
