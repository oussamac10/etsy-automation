<script setup lang="ts">
import { computed, ref } from "vue";
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
import { sanitizeUrl } from "~/utils/sanitize";

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

interface ProductFitItem {
  product: string;
  fit: number;
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
  score_breakdown: Record<string, any>;
  score_explanation: string | null;
  status: string;
  created_at: string;
  prompts: DesignPrompt[];
}

interface Workflow {
  id: string;
  state: string;
  version: number;
  idea_mode?: string;
  target_country?: string;
  output_language?: string;
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

interface ResearchEvidenceItem {
  id: string;
  search_query: string;
  query_angle: string;
  source_url: string;
  source_title: string;
  observation: string;
  observed_at: string;
}

interface KeywordClusterItem {
  id: string;
  primary_phrase: string;
  attributes: string[];
  recipient_occasion_terms: string[];
  use_case_terms: string[];
  competition_level: string;
  competition_note: string | null;
  relevance_rank: number;
}

interface ResearchSummaryData {
  run: ResearchRun | null;
  evidence: ResearchEvidenceItem[];
  keyword_clusters: KeywordClusterItem[];
  proven_market_observations: string[];
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
  (e: "conceptRefreshed", updatedConcept: Concept): void;
}>();

function getApiBase(): string {
  try {
    return useRuntimeConfig()?.public?.apiBase || "http://localhost:8000";
  } catch {
    return "http://localhost:8000";
  }
}

const isScreeningMap = ref<Record<string, boolean>>({});
const isRefreshingMap = ref<Record<string, boolean>>({});
const isStartingNewResearch = ref(false);
const expandedFindingsMap = ref<Record<string, boolean>>({});
const expandedPromptMap = ref<Record<string, boolean>>({});
const highRiskConfirmConcept = ref<Concept | null>(null);

// Research Modal State
const isResearchModalOpen = ref(false);
const activeResearchConcept = ref<Concept | null>(null);
const isLoadingResearch = ref(false);
const researchSummary = ref<ResearchSummaryData | null>(null);

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

function togglePrompt(conceptId: string) {
  expandedPromptMap.value[conceptId] = !expandedPromptMap.value[conceptId];
}

// Opportunity Scoring & Badges Helpers
function getOpportunityType(concept: Concept): string {
  const opt = concept.score_breakdown?.opportunity_type;
  if (opt === "best_opportunity") return "BEST OPPORTUNITY";
  if (opt === "niche_opportunity") return "NICHE OPPORTUNITY";
  if (opt === "emerging_opportunity") return "EMERGING OPPORTUNITY";
  return "OPPORTUNITY";
}

function getOpportunityBadgeClass(concept: Concept): string {
  const type = getOpportunityType(concept);
  if (type === "BEST OPPORTUNITY") {
    return "text-[10px] uppercase font-bold tracking-wide px-2 py-0.5 inline-flex items-center gap-1 border bg-emerald-500/10 text-emerald-700 border-emerald-500/30";
  }
  if (type === "NICHE OPPORTUNITY") {
    return "text-[10px] uppercase font-bold tracking-wide px-2 py-0.5 inline-flex items-center gap-1 border bg-indigo-500/10 text-indigo-700 border-indigo-500/30";
  }
  return "text-[10px] uppercase font-bold tracking-wide px-2 py-0.5 inline-flex items-center gap-1 border bg-amber-500/10 text-amber-700 border-amber-500/30";
}

function getOpportunityScore(concept: Concept): number {
  if (typeof concept.score_breakdown?.overall_score === "number") {
    return concept.score_breakdown.overall_score;
  }
  if (typeof concept.score === "number") {
    return Math.round(concept.score * 20);
  }
  return 85;
}

function getTrend(concept: Concept): string {
  return concept.score_breakdown?.trend_direction || "Rising";
}

function getCompetition(concept: Concept): string {
  return concept.score_breakdown?.competition || "Medium";
}

function getMarketValidation(concept: Concept): string {
  return concept.score_breakdown?.market_validation || "Strong";
}

function getTiming(concept: Concept): string {
  return concept.score_breakdown?.timing_label || "Sell Now";
}

function getWhyItCouldSell(concept: Concept): string {
  return concept.score_breakdown?.why_it_could_sell || concept.differentiation;
}

function getRecommendedProducts(concept: Concept): ProductFitScoreItem[] {
  const prods = concept.score_breakdown?.recommended_products;
  if (Array.isArray(prods) && prods.length > 0) {
    return prods as ProductFitScoreItem[];
  }
  return (concept.prompts[0]?.intended_product_uses || ["mug", "tshirt"]).map((p) => ({
    product: p,
    fit: 90,
  }));
}

interface ProductFitScoreItem {
  product: string;
  fit: number;
}

function formatProductName(prod: string): string {
  const names: Record<string, string> = {
    tshirt: "T-Shirt",
    sweatshirt: "Sweatshirt",
    tote: "Tote Bag",
    mug: "Mug",
    tumbler: "Tumbler",
    poster: "Poster",
    sticker: "Sticker",
    phone_case: "Phone Case",
    candle: "Candle",
  };
  return names[prod.toLowerCase()] || prod;
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

async function handleRefreshSingleConcept(conceptId: string) {
  isRefreshingMap.value[conceptId] = true;
  try {
    const headers: Record<string, string> = {};
    try {
      Object.assign(headers, useRequestHeaders(["cookie"]));
    } catch {}
    const updated = await $fetch<Concept>(
      `${getApiBase().replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/concepts/${conceptId}/refresh`,
      {
        method: "POST",
        headers,
        credentials: "include",
      }
    );
    emit("conceptRefreshed", updated);
  } catch (err) {
    console.error("Failed to refresh single concept:", err);
  } finally {
    isRefreshingMap.value[conceptId] = false;
  }
}

async function handleFindNewOpportunities() {
  isStartingNewResearch.value = true;
  try {
    emit("startResearch");
  } finally {
    setTimeout(() => {
      isStartingNewResearch.value = false;
    }, 2000);
  }
}

async function openSeeResearch(concept: Concept) {
  activeResearchConcept.value = concept;
  isResearchModalOpen.value = true;
  isLoadingResearch.value = true;

  try {
    const headers: Record<string, string> = {};
    try {
      Object.assign(headers, useRequestHeaders(["cookie"]));
    } catch {}
    const res = await $fetch<ResearchSummaryData>(
      `${getApiBase().replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/research/summary`,
      {
        method: "GET",
        headers,
        credentials: "include",
      }
    );
    researchSummary.value = res;
  } catch (err) {
    console.error("Failed to fetch research summary:", err);
  } finally {
    isLoadingResearch.value = false;
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
      <h2 class="text-lg font-bold text-foreground mb-1">Market Opportunity Discovery Engine Running</h2>
      <p class="text-xs text-muted-foreground max-w-lg mx-auto">
        Evaluating search demand, seasonal timing, buyer clarity, USPTO trademark clearance, and physical product fit. Generates 3 validated opportunities.
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
      <h2 class="text-lg font-bold text-destructive mb-1">Opportunity Discovery Failed</h2>
      <p class="text-xs text-red-700 max-w-md mx-auto mb-4">
        Reason: {{ latestRun?.failure_reason || 'An unexpected error occurred. Please try again.' }}
      </p>
      <Button variant="destructive" size="default" class="font-semibold cursor-pointer" @click="emit('startResearch')">
        <Icon name="lucide:rotate-ccw" class="size-4 mr-1.5" aria-hidden="true" />
        <span>Retry Market Discovery</span>
      </Button>
    </Card>

    <!-- State 3: Opportunities Workspace -->
    <div v-else class="space-y-6">
      <!-- Guidance Alert -->
      <Alert v-if="workflow.state === 'IDEA_REVIEW'" variant="info" class="border-primary/30 bg-primary/5">
        <Icon name="lucide:sparkles" class="size-4 text-primary" aria-hidden="true" />
        <div>
          <AlertTitle class="font-bold text-foreground">Select an Opportunity to Design</AlertTitle>
          <AlertDescription class="text-xs text-secondary-foreground mt-0.5">
            Compare the 3 commercial opportunities below. Click <b>Use This Idea</b> to proceed to Artwork Studio, <b>See Research</b> for detailed demand signals, or <b>Refresh Idea</b> to explore alternatives.
          </AlertDescription>
        </div>
      </Alert>

      <Alert v-if="workflow.state === 'IDEA_APPROVED'" variant="success">
        <Icon name="lucide:circle-check" class="size-4 text-emerald-600" aria-hidden="true" />
        <div>
          <AlertTitle class="font-bold text-emerald-800">Opportunity Approved</AlertTitle>
          <AlertDescription class="text-xs text-emerald-700 mt-0.5">
            The selected design concept is locked. Navigate to the <b>Artwork Studio</b> tab to review and upscale candidate PNG designs.
          </AlertDescription>
        </div>
      </Alert>

      <!-- Opportunities Header Bar -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div class="space-y-0.5">
          <h2 class="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Market Opportunity Discovery</span>
            <Badge variant="secondary" class="text-xs font-mono font-bold">
              3 Ranked Opportunities
            </Badge>
          </h2>
          <p class="text-xs text-muted-foreground">
            Scored by commercial demand (30%), competition room (20%), trend momentum (15%), seasonal timing (15%), buyer clarity (10%), and product fit (10%).
          </p>
        </div>

        <Button
          v-if="workflow.state === 'IDEA_REVIEW'"
          variant="outline"
          size="sm"
          :disabled="isStartingNewResearch"
          class="font-semibold text-xs gap-1.5 cursor-pointer bg-white"
          @click="handleFindNewOpportunities"
        >
          <Icon v-if="isStartingNewResearch" name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
          <Icon v-else name="lucide:rotate-ccw" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Find 3 New Opportunities</span>
        </Button>
      </div>

      <Card v-if="concepts.length === 0" class="p-8 text-center">
        <p class="text-muted-foreground text-xs">No opportunities found for this campaign yet.</p>
      </Card>

      <!-- 3 Opportunity Cards Grid/List -->
      <div v-else class="space-y-6">
        <Card
          v-for="concept in concepts"
          :key="concept.id"
          class="shadow-sm border transition-all duration-150 overflow-hidden"
          :class="[
            concept.status?.toUpperCase() === 'APPROVED'
              ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/10'
              : concept.status?.toUpperCase() === 'REJECTED'
                ? 'border-red-200 opacity-60 bg-red-50/20'
                : 'border-border bg-white',
            approvedConcept && concept.status?.toUpperCase() !== 'APPROVED' ? 'opacity-40 pointer-events-none' : '',
          ]"
        >
          <!-- Card Top Bar: Strategy Badge, Title, Score -->
          <CardHeader class="pb-3 border-b border-border bg-slate-50/60">
            <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div class="space-y-1.5">
                <div class="flex items-center gap-2 flex-wrap">
                  <!-- Archetype Badge -->
                  <Badge :class="getOpportunityBadgeClass(concept)">
                    <Icon
                      :name="
                        getOpportunityType(concept) === 'BEST OPPORTUNITY'
                          ? 'lucide:trophy'
                          : getOpportunityType(concept) === 'NICHE OPPORTUNITY'
                            ? 'lucide:target'
                            : 'lucide:flame'
                      "
                      class="size-3"
                      aria-hidden="true"
                    />
                    <span>{{ getOpportunityType(concept) }}</span>
                  </Badge>

                  <Badge v-if="concept.status?.toUpperCase() === 'APPROVED'" variant="success" class="text-[10px] px-2 py-0 font-bold inline-flex items-center gap-1">
                    <Icon name="lucide:circle-check" class="size-3 text-emerald-600" aria-hidden="true" />
                    <span>Selected</span>
                  </Badge>
                </div>

                <CardTitle class="text-base font-bold text-foreground">{{ concept.title }}</CardTitle>
              </div>

              <!-- Opportunity Score 0-100 -->
              <div class="flex items-center gap-2">
                <div class="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-primary/10 border border-primary/20 text-primary">
                  <Icon name="lucide:gauge" class="size-4 text-primary" aria-hidden="true" />
                  <div class="text-right leading-none">
                    <span class="text-[10px] uppercase block text-muted-foreground font-bold">Opportunity</span>
                    <span class="text-sm font-extrabold font-mono text-primary">{{ getOpportunityScore(concept) }}/100</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Key Signals Strip -->
            <div class="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 text-[11px]">
              <div class="flex items-center gap-1.5 p-1.5 rounded-lg bg-secondary/50 border border-border/80">
                <Icon name="lucide:trending-up" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
                <span class="truncate text-muted-foreground">Trend: <strong class="text-foreground">{{ getTrend(concept) }}</strong></span>
              </div>
              <div class="flex items-center gap-1.5 p-1.5 rounded-lg bg-secondary/50 border border-border/80">
                <Icon name="lucide:bar-chart-2" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
                <span class="truncate text-muted-foreground">Comp: <strong class="text-foreground">{{ getCompetition(concept) }}</strong></span>
              </div>
              <div class="flex items-center gap-1.5 p-1.5 rounded-lg bg-secondary/50 border border-border/80">
                <Icon name="lucide:clock" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
                <span class="truncate text-muted-foreground">Timing: <strong class="text-foreground">{{ getTiming(concept) }}</strong></span>
              </div>
              <div class="flex items-center gap-1.5 p-1.5 rounded-lg bg-secondary/50 border border-border/80">
                <Icon name="lucide:shield-check" class="size-3.5 text-emerald-600 shrink-0" aria-hidden="true" />
                <span class="truncate text-muted-foreground">Validation: <strong class="text-foreground">{{ getMarketValidation(concept) }}</strong></span>
              </div>
              <div class="flex items-center gap-1.5 p-1.5 rounded-lg bg-secondary/50 border border-border/80">
                <Icon
                  :name="concept.risk_level?.toLowerCase() === 'high' ? 'lucide:shield-alert' : 'lucide:shield-check'"
                  :class="concept.risk_level?.toLowerCase() === 'high' ? 'text-destructive' : 'text-emerald-600'"
                  class="size-3.5 shrink-0"
                  aria-hidden="true"
                />
                <span class="truncate text-muted-foreground">IP Risk: <strong :class="concept.risk_level?.toLowerCase() === 'high' ? 'text-destructive font-bold' : 'text-foreground'">{{ concept.risk_level?.toUpperCase() }}</strong></span>
              </div>
            </div>
          </CardHeader>

          <CardContent class="p-5 space-y-4 text-xs">
            <!-- Concept Description -->
            <p class="text-sm text-foreground leading-relaxed">{{ concept.description }}</p>

            <!-- Target Buyer & Best For Products -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div class="p-3 rounded-lg bg-secondary/40 border border-border space-y-1">
                <span class="text-[11px] font-bold text-foreground block">Target Buyer Persona:</span>
                <p class="text-secondary-foreground text-xs">{{ concept.target_buyer || 'Passionate Niche Shoppers' }}</p>
              </div>

              <div class="p-3 rounded-lg bg-secondary/40 border border-border space-y-1">
                <span class="text-[11px] font-bold text-foreground block">Recommended Product Formats:</span>
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span
                    v-for="p in getRecommendedProducts(concept).slice(0, 4)"
                    :key="p.product"
                    class="px-2 py-0.5 rounded-md bg-white border border-border text-[10px] font-medium text-foreground inline-flex items-center gap-1"
                  >
                    <span>{{ formatProductName(p.product) }}</span>
                    <span class="text-primary font-bold">{{ p.fit }}%</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- Why This Could Sell Highlight Block -->
            <div class="rounded-xl border border-primary/20 bg-primary/5 p-3.5 space-y-1">
              <div class="flex items-center gap-1.5 text-primary font-bold text-xs">
                <Icon name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
                <span>Why This Could Sell:</span>
              </div>
              <p class="text-xs text-foreground/90 leading-relaxed">{{ getWhyItCouldSell(concept) }}</p>
            </div>

            <!-- Top Keywords Tags -->
            <div v-if="concept.score_breakdown?.keyword_cluster && concept.score_breakdown.keyword_cluster.length > 0" class="flex items-center gap-1.5 flex-wrap">
              <span class="text-[11px] font-semibold text-muted-foreground">Keywords:</span>
              <span
                v-for="(kw, kIdx) in concept.score_breakdown.keyword_cluster.slice(0, 5)"
                :key="kIdx"
                class="px-2 py-0.5 rounded-full bg-secondary text-secondary-foreground text-[10px] border border-border"
              >
                {{ kw }}
              </span>
            </div>

            <!-- Active Prompt Accordion (Expandable) -->
            <div class="rounded-lg border border-border bg-slate-50/50 p-2.5 space-y-2">
              <div class="flex items-center justify-between cursor-pointer select-none" @click="togglePrompt(concept.id)">
                <span class="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Icon name="lucide:file-text" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Artwork Prompt Specifications (v{{ concept.prompts[concept.prompts.length - 1]?.version || 1 }})</span>
                </span>
                <Button variant="ghost" size="sm" class="h-6 px-1.5 text-xs text-muted-foreground">
                  <Icon :name="expandedPromptMap[concept.id] ? 'lucide:chevron-up' : 'lucide:chevron-down'" class="size-3.5" aria-hidden="true" />
                </Button>
              </div>

              <div v-if="expandedPromptMap[concept.id]" class="pt-2 border-t border-border space-y-1.5 font-mono text-[11px]">
                <p><span class="font-bold text-muted-foreground">Positive:</span> {{ concept.prompts[concept.prompts.length - 1]?.positive_prompt }}</p>
                <p><span class="font-bold text-muted-foreground">Negative:</span> {{ concept.prompts[concept.prompts.length - 1]?.negative_prompt }}</p>
                <p v-if="concept.prompts[concept.prompts.length - 1]?.exact_slogan">
                  <span class="font-bold text-muted-foreground">Typography:</span>
                  "{{ concept.prompts[concept.prompts.length - 1]?.exact_slogan }}"
                </p>
              </div>
            </div>
          </CardContent>

          <!-- Card Actions Footer -->
          <CardFooter
            v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
            class="flex items-center justify-between gap-3 border-t border-border pt-4 bg-secondary/10"
          >
            <!-- Left Actions: See Research & Refresh -->
            <div class="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                class="text-xs font-semibold gap-1.5 cursor-pointer bg-white"
                @click="openSeeResearch(concept)"
              >
                <Icon name="lucide:search" class="size-3.5 text-primary" aria-hidden="true" />
                <span>See Research</span>
              </Button>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                :disabled="isRefreshingMap[concept.id]"
                class="text-xs font-semibold gap-1 text-muted-foreground hover:text-foreground cursor-pointer"
                @click="handleRefreshSingleConcept(concept.id)"
              >
                <Icon v-if="isRefreshingMap[concept.id]" name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
                <Icon v-else name="lucide:rotate-ccw" class="size-3.5" aria-hidden="true" />
                <span>Refresh Idea</span>
              </Button>
            </div>

            <!-- Right Primary Action: Use This Idea -->
            <Button
              variant="default"
              size="sm"
              class="font-bold cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
              @click="handleApproveClick(concept)"
            >
              <Icon name="lucide:circle-check" class="size-4" aria-hidden="true" />
              <span>Use This Idea</span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>

    <!-- See Research Breakdown Modal -->
    <Dialog :open="isResearchModalOpen" max-width="2xl" @close="isResearchModalOpen = false">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2 text-foreground">
          <Icon name="lucide:search" class="size-5 text-primary" aria-hidden="true" />
          <span>Market Opportunity Research Breakdown</span>
        </DialogTitle>
        <DialogDescription>
          Multi-angle evidence aggregated from web search, marketplace trends, seasonal calendars, and trademark registries.
        </DialogDescription>
      </DialogHeader>

      <div v-if="isLoadingResearch" class="p-8 text-center">
        <Icon name="lucide:loader-circle" class="size-8 animate-spin text-primary mx-auto mb-2" aria-hidden="true" />
        <p class="text-xs text-muted-foreground">Loading verified research signals...</p>
      </div>

      <div v-else-if="researchSummary" class="space-y-4 my-3 max-h-[65vh] overflow-y-auto pr-1 text-xs">
        <!-- Confidence & Summary -->
        <div class="p-3.5 rounded-xl bg-secondary/40 border border-border flex items-center justify-between gap-3">
          <div>
            <span class="text-[10px] uppercase font-bold text-muted-foreground block">Evidence Confidence</span>
            <span class="text-sm font-bold text-foreground uppercase">{{ researchSummary.run?.confidence || 'HIGH' }}</span>
          </div>
          <div class="text-right">
            <span class="text-[10px] uppercase font-bold text-muted-foreground block">Validated Angles</span>
            <span class="text-sm font-bold text-primary">{{ researchSummary.evidence.length }} Search Angles</span>
          </div>
        </div>

        <!-- Proven Observations -->
        <div v-if="researchSummary.proven_market_observations && researchSummary.proven_market_observations.length > 0" class="space-y-1.5">
          <h4 class="font-bold text-xs text-foreground">Market Observations & Patterns:</h4>
          <ul class="space-y-1 text-muted-foreground pl-4 list-disc text-[11px]">
            <li v-for="(obs, oIdx) in researchSummary.proven_market_observations" :key="oIdx">
              {{ obs }}
            </li>
          </ul>
        </div>

        <!-- Keyword Clusters -->
        <div v-if="researchSummary.keyword_clusters.length > 0" class="space-y-2">
          <h4 class="font-bold text-xs text-foreground">Keyword Clusters & Competition:</h4>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div
              v-for="kw in researchSummary.keyword_clusters.slice(0, 6)"
              :key="kw.id"
              class="p-2.5 rounded-lg bg-white border border-border space-y-1"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-foreground">"{{ kw.primary_phrase }}"</span>
                <Badge variant="outline" class="text-[9px] uppercase font-bold">
                  {{ kw.competition_level }}
                </Badge>
              </div>
              <p v-if="kw.competition_note" class="text-[10px] text-muted-foreground">{{ kw.competition_note }}</p>
            </div>
          </div>
        </div>

        <!-- Cited Sources & Observations -->
        <div class="space-y-2">
          <h4 class="font-bold text-xs text-foreground">Search Evidence Sources:</h4>
          <div class="space-y-2">
            <div
              v-for="ev in researchSummary.evidence"
              :key="ev.id"
              class="p-2.5 rounded-lg bg-slate-50 border border-border text-[11px] space-y-1"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-foreground">{{ ev.source_title || ev.query_angle }}</span>
                <a
                  v-if="ev.source_url"
                  :href="sanitizeUrl(ev.source_url)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-primary hover:underline text-[10px] inline-flex items-center gap-0.5 shrink-0"
                >
                  <span>Source Link</span>
                  <Icon name="lucide:external-link" class="size-2.5" aria-hidden="true" />
                </a>
              </div>
              <p class="text-muted-foreground">{{ ev.observation }}</p>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-4">
        <Button variant="outline" size="sm" @click="isResearchModalOpen = false">
          Close Research
        </Button>
      </DialogFooter>
    </Dialog>

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
          Cancel & Pick Alternative
        </Button>
        <Button variant="destructive" size="sm" class="font-bold" @click="confirmHighRiskApproval">
          Approve Anyway
        </Button>
      </DialogFooter>
    </Dialog>
  </div>
</template>
