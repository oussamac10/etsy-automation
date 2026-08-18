<script setup lang="ts">
import { ref } from "vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardContent from "~/components/ui/CardContent.vue";
import CardFooter from "~/components/ui/CardFooter.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Dialog from "~/components/ui/Dialog.vue";
import DialogHeader from "~/components/ui/DialogHeader.vue";
import DialogTitle from "~/components/ui/DialogTitle.vue";
import DialogDescription from "~/components/ui/DialogDescription.vue";
import DialogFooter from "~/components/ui/DialogFooter.vue";

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

interface TrademarkFinding {
  mark_text?: string;
  serial_number?: string | null;
  registration_number?: string | null;
  status?: string;
  is_live: boolean;
  goods_services?: string | null;
  classes?: string[];
  owner?: string | null;
  filing_date?: string | null;
  registration_date?: string | null;
  source_url?: string | null;
  tsdr_verified?: boolean;
}

interface TrademarkReport {
  screening_source?: string;
  uspto_status?: string;
  risk_level?: string;
  match_count?: number;
  matches?: TrademarkFinding[];
  reasons?: string[];
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
  score_breakdown: Record<string, unknown>;
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
  (e: "screenTrademark", conceptId: string): void;
}>();

const isScreeningMap = ref<Record<string, boolean>>({});
const expandedFindingsMap = ref<Record<string, boolean>>({});
const highRiskConfirmConcept = ref<Concept | null>(null);

function getTrademarkReport(concept: Concept): TrademarkReport | null {
  const report = concept.score_breakdown?.trademark_report;
  if (report && typeof report === "object") {
    return report as TrademarkReport;
  }
  return null;
}

function getMatches(concept: Concept): TrademarkFinding[] {
  const report = getTrademarkReport(concept);
  return report?.matches || [];
}

function hasLiveMatches(concept: Concept): boolean {
  const matches = getMatches(concept);
  return matches.some((m) => m.is_live);
}

function hasDeadMatches(concept: Concept): boolean {
  const matches = getMatches(concept);
  return matches.length > 0 && !hasLiveMatches(concept);
}

function toggleFindings(conceptId: string) {
  expandedFindingsMap.value[conceptId] = !expandedFindingsMap.value[conceptId];
}

async function handleScreenTrademark(conceptId: string) {
  isScreeningMap.value[conceptId] = true;
  try {
    emit("screenTrademark", conceptId);
  } finally {
    setTimeout(() => {
      isScreeningMap.value[conceptId] = false;
    }, 1500);
  }
}

function handleApproveClick(concept: Concept) {
  if (concept.risk_level?.toLowerCase() === "high" || hasLiveMatches(concept)) {
    highRiskConfirmConcept.value = concept;
  } else {
    emit("decideGate", concept.id, "APPROVED");
  }
}

function confirmHighRiskApproval() {
  if (highRiskConfirmConcept.value) {
    emit("decideGate", highRiskConfirmConcept.value.id, "APPROVED");
    highRiskConfirmConcept.value = null;
  }
}
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
        Our background worker is analyzing seasonal marketplace demand, matching keyword query angles, screening USPTO trademarks, and drafting structured prompts. This will automatically refresh.
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
            Review the AI-generated concepts and early USPTO trademark clearance below. Approve your preferred concept to proceed to Phase 6 Artwork Generation.
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
          <p class="text-xs text-muted-foreground">Ranked by commercial viability, competition gap, and early USPTO trademark safety</p>
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
                <span>{{ concept.score ? Number(concept.score).toFixed(2) : 'N/A' }} / 5.0</span>
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

            <!-- USPTO Early Trademark Clearance Section -->
            <div
              class="rounded-lg border p-3.5 space-y-2.5 transition-colors"
              :class="[
                concept.risk_level?.toLowerCase() === 'high' || hasLiveMatches(concept)
                  ? 'bg-red-50/70 border-red-200 text-red-950'
                  : hasDeadMatches(concept) || concept.risk_level?.toLowerCase() === 'medium'
                    ? 'bg-amber-50/70 border-amber-200 text-amber-950'
                    : 'bg-emerald-50/50 border-emerald-200 text-emerald-950'
              ]"
            >
              <div class="flex items-center justify-between gap-2 flex-wrap">
                <div class="flex items-center gap-2">
                  <Icon
                    v-if="concept.risk_level?.toLowerCase() === 'high' || hasLiveMatches(concept)"
                    name="lucide:shield-alert"
                    class="size-4 text-destructive shrink-0"
                    aria-hidden="true"
                  />
                  <Icon
                    v-else-if="hasDeadMatches(concept) || concept.risk_level?.toLowerCase() === 'medium'"
                    name="lucide:shield-alert"
                    class="size-4 text-amber-600 shrink-0"
                    aria-hidden="true"
                  />
                  <Icon
                    v-else
                    name="lucide:shield-check"
                    class="size-4 text-emerald-600 shrink-0"
                    aria-hidden="true"
                  />

                  <div>
                    <span class="font-bold text-xs">
                      {{
                        concept.risk_level?.toLowerCase() === 'high' || hasLiveMatches(concept)
                          ? 'HIGH RISK: Active USPTO Registered Trademark'
                          : hasDeadMatches(concept) || concept.risk_level?.toLowerCase() === 'medium'
                            ? 'USPTO Notice: Inactive / DEAD Mark Match'
                            : 'USPTO Trademark Cleared'
                      }}
                    </span>
                  </div>
                </div>

                <div class="flex items-center gap-1.5">
                  <Button
                    v-if="getMatches(concept).length > 0"
                    type="button"
                    variant="ghost"
                    size="sm"
                    class="h-6 px-2 text-[11px] gap-1 cursor-pointer"
                    @click="toggleFindings(concept.id)"
                  >
                    <span>{{ getMatches(concept).length }} {{ getMatches(concept).length === 1 ? 'Match' : 'Matches' }}</span>
                    <Icon :name="expandedFindingsMap[concept.id] ? 'lucide:chevron-up' : 'lucide:chevron-down'" class="size-3" aria-hidden="true" />
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    :disabled="isScreeningMap[concept.id]"
                    class="h-6 px-2 text-[11px] gap-1 bg-white/80 cursor-pointer"
                    @click="handleScreenTrademark(concept.id)"
                  >
                    <Icon v-if="isScreeningMap[concept.id]" name="lucide:loader-circle" class="size-3 animate-spin text-primary" aria-hidden="true" />
                    <Icon v-else name="lucide:rotate-ccw" class="size-3" aria-hidden="true" />
                    <span>Re-screen</span>
                  </Button>
                </div>
              </div>

              <p class="text-[11px] leading-relaxed opacity-90">
                {{ concept.risk_note || (hasLiveMatches(concept) ? 'Active registered trademark found in Class 025/009.' : hasDeadMatches(concept) ? 'Historical match found, but the mark is officially DEAD/cancelled in USPTO.' : 'No conflicting active registered marks in apparel or printable digital goods.') }}
              </p>

              <!-- Expandable Registry Findings List -->
              <div v-if="expandedFindingsMap[concept.id] && getMatches(concept).length > 0" class="pt-2 border-t border-current/10 space-y-2">
                <div
                  v-for="(match, mIdx) in getMatches(concept)"
                  :key="mIdx"
                  class="bg-white/90 p-2.5 rounded border border-current/20 space-y-1 text-[11px] text-foreground"
                >
                  <div class="flex items-center justify-between gap-2 flex-wrap">
                    <span class="font-bold font-mono">"{{ match.mark_text || 'UNKNOWN MARK' }}"</span>
                    <div class="flex items-center gap-1.5">
                      <Badge
                        :variant="match.is_live ? 'destructive' : 'secondary'"
                        class="text-[9px] px-1.5 py-0 uppercase font-mono font-bold"
                      >
                        {{ match.is_live ? 'LIVE' : 'DEAD / CANCELLED' }}
                      </Badge>
                      <a
                        v-if="match.source_url || match.serial_number"
                        :href="match.source_url || `https://tsdr.uspto.gov/#caseNumber=${match.serial_number}&caseSearchType=US_APPLICATION&caseType=DEFAULT&searchType=statusSearch`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-primary hover:underline text-[10px] inline-flex items-center gap-0.5"
                      >
                        <span>TSDR Case</span>
                        <Icon name="lucide:external-link" class="size-2.5" aria-hidden="true" />
                      </a>
                    </div>
                  </div>
                  <p v-if="match.owner" class="text-muted-foreground text-[10px]">
                    <span class="font-medium text-foreground">Owner:</span> {{ match.owner }}
                  </p>
                  <p v-if="match.goods_services" class="text-muted-foreground text-[10px] line-clamp-2">
                    <span class="font-medium text-foreground">Classes/Goods:</span> {{ match.goods_services }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Score Breakdown -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-border">
              <template v-for="(val, key) in concept.score_breakdown" :key="key">
                <div v-if="key !== 'trademark_report' && typeof val === 'number'" class="bg-secondary/40 p-2 rounded border border-border">
                  <span class="text-muted-foreground uppercase tracking-wider block text-[10px]">{{ String(key).replace('_', ' ') }}</span>
                  <span class="text-foreground font-bold text-xs">{{ val }} / 5</span>
                </div>
              </template>
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
              @click="handleApproveClick(concept)"
            >
              <Icon name="lucide:circle-check" class="size-3.5" aria-hidden="true" />
              <span>Approve This Concept</span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>

    <!-- High Risk Approval Confirmation Dialog -->
    <Dialog :open="highRiskConfirmConcept !== null" max-width="md" @close="highRiskConfirmConcept = null">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2 text-destructive">
          <Icon name="lucide:shield-alert" class="size-5" aria-hidden="true" />
          <span>High Trademark Risk Warning</span>
        </DialogTitle>
        <DialogDescription>
          This concept or slogan has flagged an active LIVE registered trademark in the USPTO database. Generating artwork for this phrase may lead to listing takedowns on Etsy.
        </DialogDescription>
      </DialogHeader>

      <div v-if="highRiskConfirmConcept" class="p-3 bg-red-50 rounded-lg border border-red-200 text-xs text-red-900 space-y-1 my-2">
        <p class="font-bold">{{ highRiskConfirmConcept.title }}</p>
        <p class="text-[11px] text-red-700">{{ highRiskConfirmConcept.risk_note }}</p>
      </div>

      <DialogFooter class="gap-2 mt-4">
        <Button variant="outline" size="sm" @click="highRiskConfirmConcept = null">
          Cancel & Edit Slogan
        </Button>
        <Button variant="destructive" size="sm" class="font-bold" @click="confirmHighRiskApproval">
          Approve Anyway
        </Button>
      </DialogFooter>
    </Dialog>
  </div>
</template>
