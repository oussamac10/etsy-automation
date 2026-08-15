<script setup lang="ts">
/* global $fetch */
import { ref, onMounted, onBeforeUnmount, watch, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  canDelete,
  isRunning,
  isStopped,
  needsOwner,
  stageLabel,
  useWorkflowControls,
} from "~/composables/useWorkflowControls";
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Square,
  Trash2,
  Edit3,
  Check,
  Star,
  ChevronLeft,
  Lightbulb,
  Printer,
  Download,
  ShieldCheck,
  Image as ImageIcon,
} from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Textarea from "~/components/ui/Textarea.vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import CardFooter from "~/components/ui/CardFooter.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Dialog from "~/components/ui/Dialog.vue";
import DialogHeader from "~/components/ui/DialogHeader.vue";
import DialogTitle from "~/components/ui/DialogTitle.vue";
import DialogDescription from "~/components/ui/DialogDescription.vue";
import DialogFooter from "~/components/ui/DialogFooter.vue";

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

interface ResearchRun {
  id: string;
  status: string;
  confidence: string | null;
  proposed_test: string | null;
  started_at: string | null;
  completed_at: string | null;
  failure_reason: string | null;
}

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

const route = useRoute();
const router = useRouter();
const workflowId = route.params.id as string;
const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

// Component state
const workflow = ref<Workflow | null>(null);
const originalIdea = ref<OriginalIdea | null>(null);
const latestRun = ref<ResearchRun | null>(null);
const concepts = ref<Concept[]>([]);
const isPageLoading = ref(true);
const pageError = ref<string | null>(null);

// Editing prompt revision
const selectedConceptId = ref<string | null>(null);
const isEditingPrompt = ref(false);
const editPositivePrompt = ref("");
const editNegativePrompt = ref("");
const editSlogan = ref("");
const editTypography = ref("");
const editChangeNote = ref("");
const isSubmittingRevision = ref(false);
const revisionError = ref<string | null>(null);

// Artwork interfaces & state
interface Asset {
  id: string;
  workflow_id: string;
  artwork_job_id: string | null;
  derived_from_id: string | null;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256: string;
  width: number | null;
  height: number | null;
  has_alpha: boolean | null;
  has_transparent_pixels: boolean | null;
  provenance: Record<string, unknown>;
  created_at: string;
  url: string | null;
}

interface ArtworkJob {
  id: string;
  workflow_id: string;
  concept_id: string;
  prompt_id: string;
  provider: string;
  provider_model: string | null;
  provider_job_id: string | null;
  idempotency_key: string;
  status: string;
  attempt_count: number;
  requested_width: number | null;
  requested_height: number | null;
  quality: string | null;
  started_at: string | null;
  completed_at: string | null;
  failure_kind: string | null;
  failure_message: string | null;
  created_at: string;
  assets: Asset[];
}

// Phase 7 Production interfaces & state
interface QaReport {
  dimensions_valid: boolean;
  width: number;
  height: number;
  target_width: number;
  target_height: number;
  density_dpi: number;
  target_dpi: number;
  has_alpha: boolean;
  has_transparent_pixels: boolean;
  transparent_background_valid: boolean;
  safe_margins_valid: boolean;
  cropped_edges_detected: boolean;
  color_space: string;
  file_size_bytes: number;
  checksum_sha256: string;
  typography_applied: boolean;
  exact_slogan_recorded: string | null;
  warnings: string[];
  qa_passed: boolean;
}

interface ProductionJob {
  id: string;
  workflow_id: string;
  source_asset_id: string | null;
  output_asset_id: string | null;
  operations: string[];
  status: string;
  idempotency_key: string;
  attempt_count: number;
  qa_report: QaReport;
  qa_passed: boolean | null;
  started_at: string | null;
  completed_at: string | null;
  failure_kind: string | null;
  failure_message: string | null;
  created_at: string;
  master_asset: Asset | null;
  mockup_assets: Asset[];
  mockup_urls: Record<string, string>;
}

const artworkJobs = ref<ArtworkJob[]>([]);
const isArtworkLoading = ref(false);
const artworkError = ref<string | null>(null);
const artProvider = ref("recraft");
const artModel = ref("recraftv4_1");

const latestProductionJob = ref<ProductionJob | null>(null);
const isProductionLoading = ref(false);
const productionError = ref<string | null>(null);
const selectedMockupTab = ref<string>("tshirt");
const selectedCandidateId = ref<string | null>(null);

const chosenCandidateId = computed(() => {
  if (selectedCandidateId.value) return selectedCandidateId.value;
  if (latestProductionJob.value?.source_asset_id) return latestProductionJob.value.source_asset_id;
  const firstAsset = artworkJobs.value[0]?.assets?.[0];
  return firstAsset ? firstAsset.id : null;
});

const showRefineModal = ref(false);
const refinePrompt = ref("");
const refineChangeNote = ref("");
const refineAssetId = ref<string | null>(null);

watch(artProvider, (newVal) => {
  if (newVal === "recraft") {
    artModel.value = "recraftv4_1";
  } else {
    artModel.value = "gemini-3.1-flash-image";
  }
});

const isGate1Approved = computed(() => {
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
  ].includes(workflow.value?.state || "");
});

const approvedConcept = computed(() => {
  return concepts.value.find((c) => c.status?.toUpperCase() === "APPROVED");
});

// Polling settings
let pollInterval: ReturnType<typeof setInterval> | null = null;

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

async function loadData(silent = false): Promise<void> {
  if (!silent) isPageLoading.value = true;
  pageError.value = null;

  try {
    const wf = await $fetch<Workflow>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}`,
      { credentials: "include" }
    );
    workflow.value = wf;

    // Fetch original idea if hybrid or user-idea
    if (wf.idea_mode !== "market-led") {
      try {
        originalIdea.value = await $fetch<OriginalIdea>(
          `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/ideas`,
          { credentials: "include" }
        );
      } catch {
        originalIdea.value = null;
      }
    }

    // Fetch research runs
    const runs = await $fetch<ResearchRun[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/research`,
      { credentials: "include" }
    );
    latestRun.value = runs.length > 0 ? runs[runs.length - 1] : null;

    // Fetch concepts
    const fetchedConcepts = await $fetch<Concept[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/concepts`,
      { credentials: "include" }
    );
    // Sort concepts by score descending
    concepts.value = fetchedConcepts.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

    // Fetch artwork jobs
    try {
      artworkJobs.value = await $fetch<ArtworkJob[]>(
        `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork-jobs`,
        { credentials: "include" }
      );
    } catch {
      artworkJobs.value = [];
    }

    // Fetch production job
    try {
      latestProductionJob.value = await $fetch<ProductionJob | null>(
        `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/production`,
        { credentials: "include" }
      );
    } catch {
      latestProductionJob.value = null;
    }
  } catch {
    pageError.value = "Failed to load workflow details. Please verify your connection.";
  } finally {
    if (!silent) isPageLoading.value = false;
  }
}

async function triggerProduction(forceNew = false, candidateAssetId?: string): Promise<void> {
  isProductionLoading.value = true;
  productionError.value = null;
  const targetId = candidateAssetId || selectedCandidateId.value || latestProductionJob.value?.source_asset_id;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const job = await $fetch<ProductionJob>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/production`,
      {
        method: "POST",
        headers,
        body: { force_new: forceNew, candidate_asset_id: targetId || undefined },
        credentials: "include",
      }
    );
    latestProductionJob.value = job;
    if (targetId) selectedCandidateId.value = targetId;
    await loadData(true);
    startPolling();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string; message?: string } };
    productionError.value = errObj.data?.detail || errObj.data?.message || "Failed to trigger PNG production.";
  } finally {
    isProductionLoading.value = false;
  }
}

async function switchCandidateAndProduce(assetId: string): Promise<void> {
  selectedCandidateId.value = assetId;
  await triggerProduction(true, assetId);
}

async function startResearch(): Promise<void> {
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/research`,
      { method: "POST", headers, credentials: "include" }
    );
    await loadData();
    startPolling();
  } catch {
    pageError.value = "Failed to start research campaign.";
  }
}

async function handleDecideGate(
  conceptId: string,
  decision: "APPROVED" | "REJECTED",
  comment?: string
): Promise<void> {
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const concept = concepts.value.find((c) => c.id === conceptId);
    if (!concept) return;

    const payload = {
      gate: "IDEA_APPROVAL",
      decision,
      comment: comment || null,
      target_type: "ProductConcept",
      target_id: conceptId,
      target_version: concept.prompts[concept.prompts.length - 1]?.version || 1,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/approvals`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
  } catch {
    pageError.value = "Failed to submit decision.";
  }
}

async function startArtwork(): Promise<void> {
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      provider: artProvider.value,
      provider_model: artModel.value,
      requested_width: 1024,
      requested_height: 1024,
      quality: "standard",
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
    startPolling();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    artworkError.value = errObj.data?.detail || "Failed to trigger artwork generation.";
  } finally {
    isArtworkLoading.value = false;
  }
}

async function regenerateArtwork(provider?: string, model?: string): Promise<void> {
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      provider: provider || artProvider.value,
      provider_model: model || artModel.value,
      requested_width: 1024,
      requested_height: 1024,
      quality: "standard",
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork/regenerate`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
    startPolling();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    artworkError.value = errObj.data?.detail || "Failed to regenerate artwork.";
  } finally {
    isArtworkLoading.value = false;
  }
}

function openRefineModalForm(assetId: string) {
  refineAssetId.value = assetId;
  refinePrompt.value = "";
  refineChangeNote.value = "";
  showRefineModal.value = true;
}

async function submitRefinement(): Promise<void> {
  if (!refineAssetId.value || !refinePrompt.value || !refineChangeNote.value) return;
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      candidate_asset_id: refineAssetId.value,
      positive_prompt: refinePrompt.value,
      change_note: refineChangeNote.value,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork/refine`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    showRefineModal.value = false;
    refinePrompt.value = "";
    refineChangeNote.value = "";
    await loadData();
    startPolling();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    artworkError.value = errObj.data?.detail || "Failed to submit refinement.";
  } finally {
    isArtworkLoading.value = false;
  }
}

async function approveArtwork(assetId: string): Promise<void> {
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      gate: "ARTWORK_APPROVAL",
      decision: "APPROVED",
      target_type: "Asset",
      target_id: assetId,
      target_version: null,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/approvals`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    artworkError.value = errObj.data?.detail || "Failed to approve artwork candidate.";
  }
}

async function rejectArtwork(jobId: string, workflowVersion: number): Promise<void> {
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      gate: "ARTWORK_APPROVAL",
      decision: "REJECTED",
      target_type: "ProductWorkflow",
      target_id: workflowId,
      target_version: workflowVersion,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/approvals`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    artworkError.value = errObj.data?.detail || "Failed to reject artwork options.";
  }
}

function openReviseForm(conceptId: string): void {
  const concept = concepts.value.find((c) => c.id === conceptId);
  if (!concept) return;

  const latestPrompt = concept.prompts[concept.prompts.length - 1];
  selectedConceptId.value = conceptId;
  editPositivePrompt.value = latestPrompt?.positive_prompt || "";
  editNegativePrompt.value = latestPrompt?.negative_prompt || "";
  editSlogan.value = latestPrompt?.exact_slogan || "";
  editTypography.value = latestPrompt?.typography_instructions || "";
  editChangeNote.value = "";
  isEditingPrompt.value = true;
  revisionError.value = null;
}

async function submitRevision(): Promise<void> {
  if (!selectedConceptId.value) return;
  isSubmittingRevision.value = true;
  revisionError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      positive_prompt: editPositivePrompt.value.trim(),
      negative_prompt: editNegativePrompt.value.trim(),
      exact_slogan: editSlogan.value.trim() || null,
      typography_instructions: editTypography.value.trim() || null,
      change_note: editChangeNote.value.trim() || "Manual revision",
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/concepts/${selectedConceptId.value}/revise`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );

    isEditingPrompt.value = false;
    selectedConceptId.value = null;
    await loadData();
  } catch (err: unknown) {
    const errObj = err as { data?: { detail?: string } };
    revisionError.value = errObj.data?.detail || "Failed to submit prompt revision.";
  } finally {
    isSubmittingRevision.value = false;
  }
}

const { controlError, pendingWorkflowId, controlWorkflow } = useWorkflowControls(
  apiBase,
  () => loadData()
);

const confirmingDelete = ref(false);

async function deleteCampaign(id: string): Promise<void> {
  stopPolling();
  if (await controlWorkflow(id, "delete")) {
    await router.push("/");
  } else {
    confirmingDelete.value = false;
  }
}

const isWorkflowRunning = computed(() => {
  if (!workflow.value) return false;
  if (workflow.value.state === "PRODUCTION" && latestProductionJob.value?.status === "SUCCEEDED") {
    return false;
  }
  return isRunning(workflow.value.state);
});

const displayStageLabel = computed(() => {
  if (!workflow.value) return "";
  if (workflow.value.state === "PRODUCTION" && latestProductionJob.value?.status === "SUCCEEDED") {
    return "Production complete";
  }
  return stageLabel(workflow.value.state);
});

function startPolling(): void {
  stopPolling();
  pollInterval = setInterval(() => {
    if (isWorkflowRunning.value) {
      loadData(true);
    } else {
      stopPolling();
    }
  }, 2000);
}

function stopPolling(): void {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

onMounted(async () => {
  await loadData();
  if (isWorkflowRunning.value) {
    startPolling();
  }
});

onBeforeUnmount(stopPolling);
</script>

<template>
  <div class="min-h-screen bg-zinc-50/80 pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10">
      <!-- Loading State -->
      <div v-if="isPageLoading" class="flex flex-col items-center justify-center py-28 text-zinc-400 gap-3">
        <RotateCw class="h-8 w-8 animate-spin text-indigo-600" />
        <p class="text-sm font-medium">Fetching campaign details...</p>
      </div>

      <!-- Page Error -->
      <Alert v-else-if="pageError" variant="destructive" class="mb-8">
        <AlertCircle class="h-4 w-4" />
        <AlertTitle>Error Loading Campaign</AlertTitle>
        <AlertDescription class="flex items-center justify-between mt-2">
          <span>{{ pageError }}</span>
          <Button variant="outline" size="sm" class="h-8 text-xs" @click="() => loadData()">
            Retry
          </Button>
        </AlertDescription>
      </Alert>

      <!-- Workflow Detail Dashboard -->
      <div v-else-if="workflow" class="space-y-8">
        <!-- Campaign Header -->
        <header class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-zinc-200/80 pb-6">
          <div class="space-y-1.5">
            <div class="flex items-center gap-2 text-xs text-zinc-500">
              <NuxtLink to="/" class="flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-700">
                <ChevronLeft class="h-3.5 w-3.5" />
                <span>Campaigns</span>
              </NuxtLink>
              <span class="text-zinc-300">/</span>
              <Badge variant="secondary" class="text-[10px] px-2 py-0">
                {{ workflow.idea_mode }}
              </Badge>
            </div>
            <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900">
              {{ workflow.name }}
            </h1>
            <p class="text-xs text-zinc-400 font-mono">ID: {{ workflow.id }}</p>
          </div>

          <!-- Actions Toolbar -->
          <div class="flex items-center gap-2 flex-wrap">
            <Badge
              :variant="
                workflow.state.endsWith('_APPROVED') || workflow.state === 'ETSY_DRAFT_CREATED' || (workflow.state === 'PRODUCTION' && latestProductionJob?.status === 'SUCCEEDED')
                  ? 'success'
                  : isWorkflowRunning
                    ? 'warning'
                    : needsOwner(workflow.state)
                      ? 'default'
                      : workflow.state.endsWith('_FAILED')
                        ? 'destructive'
                        : 'secondary'
              "
              class="px-3 py-1 text-xs gap-1.5"
            >
              <span
                v-if="isWorkflowRunning"
                class="h-2 w-2 rounded-full bg-amber-500 motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <CheckCircle2
                v-else-if="workflow.state === 'PRODUCTION' && latestProductionJob?.status === 'SUCCEEDED'"
                class="h-3.5 w-3.5 text-emerald-600"
              />
              <span>{{ displayStageLabel }}</span>
            </Badge>

            <Button
              v-if="isWorkflowRunning"
              variant="destructive"
              size="sm"
              :disabled="pendingWorkflowId === workflow.id"
              class="gap-1.5"
              @click="controlWorkflow(workflow.id, 'cancel')"
            >
              <Square class="h-3.5 w-3.5 fill-current" />
              <span>Stop</span>
            </Button>

            <Button
              v-if="isStopped(workflow.state)"
              variant="default"
              size="sm"
              :disabled="pendingWorkflowId === workflow.id"
              class="gap-1.5 font-semibold shadow-2xs"
              @click="controlWorkflow(workflow.id, 'rerun')"
            >
              <RotateCw class="h-3.5 w-3.5" />
              <span>Resume</span>
            </Button>

            <Button
              v-if="canDelete(workflow.state) && !confirmingDelete"
              variant="outline"
              size="sm"
              class="gap-1.5 text-zinc-600 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50"
              @click="confirmingDelete = true"
            >
              <Trash2 class="h-3.5 w-3.5" />
              <span>Delete</span>
            </Button>

            <span
              v-else-if="confirmingDelete"
              class="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs text-rose-800"
            >
              <span>Delete this campaign?</span>
              <Button
                variant="destructive"
                size="sm"
                :disabled="pendingWorkflowId === workflow.id"
                class="h-6 px-2 text-[11px]"
                @click="deleteCampaign(workflow.id)"
              >
                Delete
              </Button>
              <Button
                variant="ghost"
                size="sm"
                class="h-6 px-2 text-[11px]"
                @click="confirmingDelete = false"
              >
                Keep
              </Button>
            </span>
          </div>
        </header>

        <Alert v-if="controlError" variant="destructive">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>{{ controlError }}</AlertDescription>
        </Alert>

        <!-- Stopped Banner -->
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
              class="gap-1.5 font-semibold shadow-2xs"
              @click="controlWorkflow(workflow.id, 'rerun')"
            >
              <RotateCw class="h-3.5 w-3.5" />
              <span>Resume from Current Step</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              :disabled="pendingWorkflowId === workflow.id"
              class="gap-1.5 text-xs text-zinc-600 border-zinc-200 bg-white hover:bg-zinc-100"
              @click="controlWorkflow(workflow.id, 'rerun', { fromScratch: true })"
            >
              <span>Restart from Brief (New Research)</span>
            </Button>
          </div>
        </Card>

        <!-- Polling / Researching State -->
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

        <!-- Failed State -->
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
          <Button variant="destructive" size="default" class="font-semibold" @click="startResearch">
            Retry Campaign Research
          </Button>
        </Card>

        <!-- Main Workspace Grid -->
        <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <!-- Concepts & Approvals (Left 2 Columns) -->
          <div class="lg:col-span-2 space-y-8">
            <!-- State Info / Guidance Alerts -->
            <Alert v-if="workflow.state === 'IDEA_REVIEW'" variant="info">
              <Sparkles class="h-4 w-4" />
              <div>
                <AlertTitle class="font-bold text-zinc-900">Choose one concept to continue.</AlertTitle>
                <AlertDescription class="text-xs text-zinc-600 mt-0.5">
                  Approve a concept to begin generating high-resolution candidate artwork options.
                </AlertDescription>
              </div>
            </Alert>

            <Alert v-if="workflow.state === 'IDEA_APPROVED' && artworkJobs.length === 0" variant="success">
              <CheckCircle2 class="h-4 w-4" />
              <div>
                <AlertTitle class="font-bold text-emerald-900">Concept approved — ready for artwork generation</AlertTitle>
                <AlertDescription class="text-xs text-emerald-700 mt-0.5">
                  Use the configuration parameters below to generate candidate designs.
                </AlertDescription>
              </div>
            </Alert>

            <!-- Phase 6: Artwork Generation & Approval Section -->
            <Card v-if="isGate1Approved" class="shadow-2xs">
              <CardHeader class="pb-4 border-b border-zinc-100">
                <div class="flex items-center justify-between">
                  <div>
                    <CardTitle class="text-lg font-bold">Phase 6: Artwork Generation & Approval</CardTitle>
                    <CardDescription>
                      Select provider/model and approve the generated candidate design.
                    </CardDescription>
                  </div>
                  <Badge v-if="workflow.state === 'ARTWORK_APPROVED'" variant="success" class="gap-1 px-3 py-1">
                    <Check class="h-3 w-3" />
                    <span>Artwork Approved</span>
                  </Badge>
                </div>
              </CardHeader>

              <CardContent class="space-y-6 pt-6">
                <!-- Selected Concept Info -->
                <div v-if="approvedConcept" class="rounded-xl border border-zinc-200/80 bg-zinc-50/60 p-4 text-sm space-y-3">
                  <div>
                    <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-700">Approved Concept</span>
                    <h4 class="text-base font-bold text-zinc-900">{{ approvedConcept.title }}</h4>
                    <p class="text-xs text-zinc-600 mt-0.5">{{ approvedConcept.description }}</p>
                  </div>

                  <div class="rounded-lg border border-zinc-200 bg-white p-3 space-y-1 text-xs font-mono">
                    <p>
                      <span class="font-bold text-zinc-400">Positive:</span>
                      {{ approvedConcept.prompts[approvedConcept.prompts.length - 1]?.positive_prompt }}
                    </p>
                    <p>
                      <span class="font-bold text-zinc-400">Negative:</span>
                      {{ approvedConcept.prompts[approvedConcept.prompts.length - 1]?.negative_prompt }}
                    </p>
                    <p v-if="approvedConcept.prompts[approvedConcept.prompts.length - 1]?.exact_slogan">
                      <span class="font-bold text-zinc-400">Slogan:</span>
                      "{{ approvedConcept.prompts[approvedConcept.prompts.length - 1]?.exact_slogan }}"
                    </p>
                  </div>
                </div>

                <!-- Inner state 1: Gate 1 approved + ready to generate artwork -->
                <div v-if="workflow.state === 'IDEA_APPROVED' && (!artworkJobs.length || !artworkJobs.some((j) => j.assets && j.assets.length > 0))" class="space-y-4">
                  <div class="rounded-xl bg-indigo-50/60 border border-indigo-200 p-4 text-xs text-zinc-700 font-medium">
                    Your concept is approved. Generate artwork to continue.
                  </div>

                  <!-- Parameters selection -->
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div class="space-y-1.5">
                      <Label for="image-provider">Image Provider</Label>
                      <select
                        id="image-provider"
                        v-model="artProvider"
                        class="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                      >
                        <option value="recraft">Recraft V4.1 (Vector & Illustration)</option>
                        <option value="gemini">Google Gemini (Photo & Creative)</option>
                      </select>
                    </div>
                    <div v-if="artProvider === 'recraft'" class="space-y-1.5">
                      <Label for="model-profile">Model Profile</Label>
                      <select
                        id="model-profile"
                        v-model="artModel"
                        class="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                      >
                        <option value="recraftv4_1">Recraft V4.1 (Standard)</option>
                        <option value="recraftv4_1_pro">Recraft V4.1 Pro (Premium, 1 Candidate)</option>
                      </select>
                    </div>
                  </div>

                  <Alert v-if="artworkError" variant="destructive">
                    <AlertCircle class="h-4 w-4" />
                    <AlertDescription>{{ artworkError }}</AlertDescription>
                  </Alert>

                  <div class="flex items-center justify-between border-t border-zinc-100 pt-4">
                    <span class="text-xs text-zinc-400">Estimated cost: $0.00 (Fake Adapter)</span>
                    <Button
                      variant="default"
                      size="default"
                      :loading="isArtworkLoading"
                      class="font-bold shadow-md shadow-indigo-600/20"
                      @click="() => startArtwork()"
                    >
                      <span>Generate Artwork</span>
                    </Button>
                  </div>
                </div>

                <!-- Inner state 2: queued / running -->
                <div v-else-if="workflow.state === 'ART_QUEUED' || workflow.state === 'ART_GENERATION'" class="py-12 text-center space-y-3">
                  <RotateCw class="h-8 w-8 animate-spin text-indigo-600 mx-auto" />
                  <h4 class="text-base font-bold text-zinc-900">Artwork generation in progress...</h4>
                  <p class="text-xs text-zinc-500 max-w-sm mx-auto">
                    Artwork generation in progress. Our background worker is calling Recraft/Gemini to generate transparent-background PNG/SVG candidates matching the approved prompt. This will automatically refresh.
                  </p>
                </div>

                <!-- Inner state 3: failed -->
                <div v-else-if="workflow.state === 'ART_GENERATION_FAILED'" class="space-y-4">
                  <Alert variant="destructive">
                    <AlertCircle class="h-4 w-4" />
                    <AlertTitle>Artwork Generation Failed</AlertTitle>
                    <AlertDescription class="text-xs mt-1">
                      Reason: {{ artworkJobs[0]?.failure_message || 'An unexpected error occurred during image generation.' }}
                    </AlertDescription>
                  </Alert>

                  <div class="flex justify-center gap-3">
                    <Button variant="destructive" size="sm" @click="() => startArtwork()">
                      Retry Generation
                    </Button>
                    <Button variant="outline" size="sm" @click="() => regenerateArtwork()">
                      Reconfigure Parameters
                    </Button>
                  </div>
                </div>

                <!-- Inner state 4: completed candidates grid -->
                <div v-else-if="artworkJobs.length > 0 && artworkJobs.some((j) => j.assets && j.assets.length > 0)" class="space-y-6">
                  <div class="flex items-center justify-between">
                    <h4 class="text-sm font-bold text-zinc-800">Generated Candidate Assets</h4>
                    <Button
                      v-if="workflow.state === 'ART_REVIEW'"
                      variant="ghost"
                      size="sm"
                      class="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      @click="() => workflow && rejectArtwork(artworkJobs[0]?.id, workflow.version)"
                    >
                      Reject All Options
                    </Button>
                  </div>

                  <Alert v-if="artworkError" variant="destructive">
                    <AlertCircle class="h-4 w-4" />
                    <AlertDescription>{{ artworkError }}</AlertDescription>
                  </Alert>

                  <!-- Candidates Grid -->
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card
                      v-for="(asset, idx) in artworkJobs[0]?.assets"
                      :key="asset.id"
                      class="overflow-hidden border transition-all cursor-pointer"
                      :class="
                        asset.id === chosenCandidateId
                          ? 'border-emerald-500 ring-2 ring-emerald-500/30 bg-emerald-50/10'
                          : 'border-zinc-200 hover:border-zinc-300'
                      "
                      @click="selectedCandidateId = asset.id"
                    >
                      <div class="aspect-square bg-zinc-100 relative flex items-center justify-center p-4">
                        <img
                          v-if="asset.url"
                          :src="asset.url"
                          alt="Candidate Preview"
                          class="object-contain w-full h-full max-h-[220px]"
                        >
                        <div v-else class="text-zinc-400 text-xs">Preview Loading...</div>
                        <Badge variant="default" class="absolute top-2 left-2 text-[10px] px-2 py-0 font-mono">
                          Candidate {{ idx + 1 }}
                        </Badge>
                        <Badge
                          v-if="asset.id === chosenCandidateId"
                          variant="success"
                          class="absolute top-2 right-2 text-[10px] px-2 py-0.5 font-bold shadow-xs gap-1"
                        >
                          <CheckCircle2 class="h-3 w-3" />
                          <span>Chosen Asset</span>
                        </Badge>
                      </div>

                      <div class="p-4 border-t border-zinc-100 bg-zinc-50/50 space-y-3">
                        <div class="flex items-center justify-between text-xs text-zinc-500">
                          <span class="font-mono">{{ asset.width }}×{{ asset.height }} · {{ (asset.byte_size / 1024).toFixed(1) }} KB</span>
                          <span class="uppercase text-[10px] font-bold">{{ asset.mime_type.split('/')[1] }}</span>
                        </div>

                        <!-- Gate 2 Review Actions -->
                        <div v-if="workflow.state === 'ART_REVIEW'" class="grid grid-cols-2 gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            class="text-xs h-8"
                            @click.stop="() => openRefineModalForm(asset.id)"
                          >
                            Refine Option
                          </Button>
                          <Button
                            variant="success"
                            size="sm"
                            class="text-xs h-8 font-bold"
                            @click.stop="() => approveArtwork(asset.id)"
                          >
                            Approve Artwork
                          </Button>
                        </div>

                        <!-- Approved State: Candidate Status / Switch Action -->
                        <div v-else-if="workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'PRODUCTION' || latestProductionJob !== null">
                          <div
                            v-if="asset.id === chosenCandidateId"
                            class="flex items-center justify-center gap-1.5 py-1.5 text-xs font-bold text-emerald-700 bg-emerald-100/60 rounded-md border border-emerald-200"
                          >
                            <CheckCircle2 class="h-3.5 w-3.5" />
                            <span>Active in Master & Mockups</span>
                          </div>
                          <Button
                            v-else
                            variant="outline"
                            size="sm"
                            class="w-full text-xs font-bold text-indigo-600 border-indigo-200 hover:bg-indigo-50 gap-1.5 h-8"
                            :disabled="isProductionLoading"
                            @click.stop="() => switchCandidateAndProduce(asset.id)"
                          >
                            <Sparkles class="h-3.5 w-3.5" />
                            <span>Switch to this Candidate & Produce</span>
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>

                  <!-- Regeneration Option -->
                  <div v-if="workflow.state === 'ART_REVIEW'" class="rounded-xl border border-dashed border-zinc-200 p-4 text-center">
                    <p class="text-xs text-zinc-500 mb-2">Not satisfied with any of these candidates?</p>
                    <Button variant="outline" size="sm" class="text-xs gap-1.5" @click="() => regenerateArtwork()">
                      <RotateCw class="h-3.5 w-3.5" />
                      <span>Regenerate All Options</span>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Phase 7: PNG Production Pipeline Card -->
            <Card
              v-if="
                workflow && (
                  workflow.state === 'ARTWORK_APPROVED' ||
                  workflow.state === 'PRODUCTION' ||
                  workflow.state === 'PRODUCTION_FAILED' ||
                  latestProductionJob !== null
                )
              "
              class="shadow-sm border-zinc-200"
            >
              <CardHeader class="pb-3 border-b border-zinc-100 bg-zinc-50/50">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <Printer class="h-5 w-5 text-indigo-600" />
                    <div>
                      <CardTitle class="text-base font-bold">Phase 7: Print-Ready PNG Production</CardTitle>
                      <CardDescription class="text-xs text-zinc-500">
                        Deterministic 4500×5400 px @ 300 DPI master PNG with transparency, safe trim, slogan typography, QA & mockups
                      </CardDescription>
                    </div>
                  </div>
                  <Badge
                    v-if="latestProductionJob?.status === 'SUCCEEDED'"
                    variant="success"
                    class="gap-1 px-3 py-1 font-semibold"
                  >
                    <CheckCircle2 class="h-3.5 w-3.5" />
                    <span>Production Complete</span>
                  </Badge>
                  <Badge
                    v-else-if="workflow.state === 'PRODUCTION' || latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED'"
                    variant="warning"
                    class="gap-1 px-3 py-1 font-semibold"
                  >
                    <RotateCw class="h-3.5 w-3.5 animate-spin" />
                    <span>Processing Pipeline...</span>
                  </Badge>
                  <Badge
                    v-else-if="workflow.state === 'PRODUCTION_FAILED' || latestProductionJob?.status === 'FAILED'"
                    variant="destructive"
                    class="gap-1 px-3 py-1 font-semibold"
                  >
                    <AlertCircle class="h-3.5 w-3.5" />
                    <span>Production Failed</span>
                  </Badge>
                  <Badge
                    v-else
                    variant="secondary"
                    class="gap-1 px-3 py-1"
                  >
                    <span>Ready to Produce</span>
                  </Badge>
                </div>
              </CardHeader>

              <CardContent class="p-6 space-y-6">
                <!-- 1. Ready State: CTA to trigger production -->
                <div
                  v-if="workflow.state === 'ARTWORK_APPROVED' && (!latestProductionJob || latestProductionJob.status === 'FAILED')"
                  class="rounded-xl border border-indigo-100 bg-indigo-50/30 p-6 space-y-4"
                >
                  <div class="flex items-start justify-between gap-4">
                    <div class="space-y-1">
                      <h3 class="text-sm font-bold text-zinc-900">Artwork Approved — Ready for Master File Generation</h3>
                      <p class="text-xs text-zinc-600">
                        The approved artwork will be scaled proportionally to 4500×5400 px with 300 DPI metadata and safe margin padding.
                        <span v-if="approvedConcept?.prompts[0]?.exact_slogan" class="block mt-1 font-medium text-indigo-900">
                          Exact slogan <b>"{{ approvedConcept.prompts[0].exact_slogan }}"</b> will be deterministically rendered via SVG typography overlay.
                        </span>
                      </p>
                    </div>
                    <div class="flex flex-wrap gap-2 text-[10px] font-mono">
                      <Badge variant="outline" class="bg-white">4500×5400 px</Badge>
                      <Badge variant="outline" class="bg-white">300 DPI</Badge>
                      <Badge variant="outline" class="bg-white">sRGB PNG</Badge>
                    </div>
                  </div>

                  <Alert v-if="productionError" variant="destructive">
                    <AlertCircle class="h-4 w-4" />
                    <AlertDescription>{{ productionError }}</AlertDescription>
                  </Alert>

                  <div class="pt-2 flex items-center gap-3">
                    <Button
                      variant="default"
                      size="default"
                      class="gap-2 bg-indigo-600 hover:bg-indigo-700 font-bold px-6"
                      :disabled="isProductionLoading"
                      @click="() => triggerProduction(false)"
                    >
                      <RotateCw v-if="isProductionLoading" class="h-4 w-4 animate-spin" />
                      <Sparkles v-else class="h-4 w-4" />
                      <span>{{ isProductionLoading ? 'Queueing Production...' : 'Start PNG Production' }}</span>
                    </Button>
                  </div>
                </div>

                <!-- 2. In-Flight State: Pipeline Progress -->
                <div
                  v-if="(latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED') || (workflow.state === 'PRODUCTION' && latestProductionJob?.status !== 'SUCCEEDED' && latestProductionJob?.status !== 'FAILED')"
                  class="rounded-xl border border-zinc-200 bg-zinc-50/50 p-6 space-y-5"
                >
                  <div class="flex items-center justify-between">
                    <div class="space-y-0.5">
                      <h4 class="text-sm font-bold text-zinc-900 flex items-center gap-2">
                        <RotateCw class="h-4 w-4 text-indigo-600 animate-spin" />
                        <span>Processing Deterministic Pipeline</span>
                      </h4>
                      <p class="text-xs text-zinc-500">Transforming approved source asset into verified master print files and mockups</p>
                    </div>
                    <span class="text-xs font-mono text-zinc-400">Step 1–7</span>
                  </div>

                  <!-- 7-Step Indicator -->
                  <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 text-center text-[11px]">
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">1. Inspect</div>
                      <div class="text-[10px] text-indigo-700/70">Validate alpha</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">2. Trim</div>
                      <div class="text-[10px] text-indigo-700/70">Safe 8% margin</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">3. Upscale</div>
                      <div class="text-[10px] text-indigo-700/70">4500×5400 px</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">4. Typography</div>
                      <div class="text-[10px] text-indigo-700/70">SVG overlay</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">5. QA Report</div>
                      <div class="text-[10px] text-indigo-700/70">Verify bounds</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">6. Mockups</div>
                      <div class="text-[10px] text-indigo-700/70">T-shirt, tote, mug</div>
                    </div>
                    <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
                      <div class="font-bold mb-0.5">7. Storage</div>
                      <div class="text-[10px] text-indigo-700/70">S3 upload</div>
                    </div>
                  </div>
                </div>

                <!-- 3. Completed State: Master PNG, QA Report, Mockups -->
                <div v-if="latestProductionJob?.status === 'SUCCEEDED'" class="space-y-6">
                  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    <!-- Master PNG Preview & Download (5 cols) -->
                    <div class="lg:col-span-5 space-y-4">
                      <div class="border border-zinc-200 rounded-xl overflow-hidden bg-white shadow-2xs">
                        <div class="aspect-[45/54] relative flex items-center justify-center p-4 bg-[repeating-conic-gradient(#f4f4f5_0%_25%,#ffffff_0%_50%)] bg-[length:16px_16px]">
                          <img
                            v-if="latestProductionJob.master_asset?.url"
                            :src="latestProductionJob.master_asset.url"
                            alt="Master Production PNG"
                            class="object-contain w-full h-full max-h-[360px]"
                          >
                          <div v-else class="text-zinc-400 text-xs">Master Image Loading...</div>
                          <Badge variant="success" class="absolute top-3 left-3 text-[11px] px-2.5 py-0.5 font-bold shadow-xs">
                            Master Print PNG
                          </Badge>
                        </div>
                        <div class="p-4 border-t border-zinc-100 bg-zinc-50/50 space-y-3">
                          <div class="flex items-center justify-between text-xs text-zinc-600">
                            <span class="font-mono font-bold">{{ latestProductionJob.master_asset?.width ?? 4500 }} × {{ latestProductionJob.master_asset?.height ?? 5400 }} px</span>
                            <Badge variant="outline" class="text-[10px] font-mono bg-white">300 DPI</Badge>
                            <span class="font-mono text-zinc-500">{{ ((latestProductionJob.master_asset?.byte_size ?? 0) / (1024 * 1024)).toFixed(2) }} MB</span>
                          </div>

                          <a
                            v-if="latestProductionJob.master_asset?.url"
                            :href="latestProductionJob.master_asset.url"
                            target="_blank"
                            download="master_print.png"
                            class="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs h-9 transition-colors shadow-2xs"
                          >
                            <Download class="h-4 w-4" />
                            <span>Download Master PNG</span>
                          </a>
                        </div>
                      </div>
                    </div>

                    <!-- QA Report & Mockups (7 cols) -->
                    <div class="lg:col-span-7 space-y-6">
                      <!-- QA Report Card -->
                      <div class="border border-zinc-200 rounded-xl p-5 bg-white space-y-4 shadow-2xs">
                        <div class="flex items-center justify-between border-b border-zinc-100 pb-3">
                          <div class="flex items-center gap-2">
                            <ShieldCheck class="h-4 w-4 text-emerald-600" />
                            <h4 class="text-sm font-bold text-zinc-900">Automated QA Validation Report</h4>
                          </div>
                          <Badge
                            :variant="latestProductionJob.qa_passed ? 'success' : 'warning'"
                            class="text-[10px] font-bold px-2 py-0.5"
                          >
                            {{ latestProductionJob.qa_passed ? 'QA PASSED' : 'QA WARNINGS' }}
                          </Badge>
                        </div>

                        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Canvas Dimensions</span>
                            <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                              <Check class="h-3 w-3 text-emerald-600" />
                              {{ latestProductionJob.qa_report?.width ?? 4500 }}×{{ latestProductionJob.qa_report?.height ?? 5400 }}
                            </span>
                          </div>

                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Print Density</span>
                            <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                              <Check class="h-3 w-3 text-emerald-600" />
                              {{ latestProductionJob.qa_report?.density_dpi ?? 300 }} DPI
                            </span>
                          </div>

                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Background Alpha</span>
                            <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                              <Check class="h-3 w-3 text-emerald-600" />
                              Transparent
                            </span>
                          </div>

                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Safe Margins</span>
                            <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                              <Check class="h-3 w-3 text-emerald-600" />
                              Protected (8%)
                            </span>
                          </div>

                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Color Space</span>
                            <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                              <Check class="h-3 w-3 text-emerald-600" />
                              {{ latestProductionJob.qa_report?.color_space ?? 'sRGB' }}
                            </span>
                          </div>

                          <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                            <span class="text-[10px] text-zinc-400 block font-medium">Slogan Typography</span>
                            <span class="font-bold text-zinc-800 text-[11px] flex items-center gap-1">
                              <Check v-if="latestProductionJob.qa_report?.typography_applied" class="h-3 w-3 text-emerald-600" />
                              <span v-else class="text-zinc-400">—</span>
                              {{ latestProductionJob.qa_report?.typography_applied ? 'Applied' : 'No Slogan' }}
                            </span>
                          </div>
                        </div>

                        <div
                          v-if="latestProductionJob.qa_report?.warnings && latestProductionJob.qa_report.warnings.length > 0"
                          class="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 space-y-1"
                        >
                          <span class="font-bold text-[11px] block">QA Advisory Warnings:</span>
                          <ul class="list-disc list-inside space-y-0.5 text-[11px]">
                            <li v-for="(warn, wIdx) in latestProductionJob.qa_report.warnings" :key="wIdx">{{ warn }}</li>
                          </ul>
                        </div>
                      </div>

                      <!-- Mockup Gallery -->
                      <div class="border border-zinc-200 rounded-xl p-5 bg-white space-y-4 shadow-2xs">
                        <div class="flex flex-wrap items-center justify-between border-b border-zinc-100 pb-3 gap-2">
                          <div class="flex items-center gap-2">
                            <ImageIcon class="h-4 w-4 text-indigo-600" />
                            <h4 class="text-sm font-bold text-zinc-900">Product Mockup Gallery</h4>
                            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600 border border-zinc-200">
                              Printful Engine
                            </span>
                          </div>
                          <div class="flex flex-wrap gap-1">
                            <button
                              v-for="p in ['tshirt', 'sweatshirt', 'tote_bag', 'mug']"
                              :key="p"
                              type="button"
                              class="text-[11px] px-2.5 py-1 rounded-md font-medium transition-all"
                              :class="
                                (selectedMockupTab === p || (p === 'tote_bag' && selectedMockupTab === 'tote'))
                                  ? 'bg-zinc-900 text-white shadow-xs'
                                  : 'text-zinc-500 hover:text-zinc-900 bg-zinc-100/80 hover:bg-zinc-200'
                              "
                              @click="selectedMockupTab = p"
                            >
                              {{ p === 'tshirt' ? '👕 T-Shirt' : p === 'sweatshirt' ? '🧥 Sweatshirt' : p === 'tote_bag' ? '👜 Tote Bag' : '☕ Ceramic Mug' }}
                            </button>
                          </div>
                        </div>

                        <div class="aspect-square max-h-[280px] mx-auto bg-zinc-50 rounded-lg overflow-hidden border border-zinc-100 flex items-center justify-center p-3 relative">
                          <img
                            v-if="latestProductionJob.mockup_urls?.[selectedMockupTab] || (selectedMockupTab === 'tote_bag' && latestProductionJob.mockup_urls?.['tote']) || (selectedMockupTab === 'tote' && latestProductionJob.mockup_urls?.['tote_bag'])"
                            :src="latestProductionJob.mockup_urls?.[selectedMockupTab] || (selectedMockupTab === 'tote_bag' ? latestProductionJob.mockup_urls?.['tote'] : latestProductionJob.mockup_urls?.['tote_bag'])"
                            :alt="selectedMockupTab"
                            class="object-contain w-full h-full max-h-[260px] rounded"
                          >
                          <div v-else class="text-zinc-400 text-xs">Mockup not available</div>
                          <a
                            v-if="latestProductionJob.mockup_urls?.[selectedMockupTab] || (selectedMockupTab === 'tote_bag' && latestProductionJob.mockup_urls?.['tote']) || (selectedMockupTab === 'tote' && latestProductionJob.mockup_urls?.['tote_bag'])"
                            :href="latestProductionJob.mockup_urls?.[selectedMockupTab] || (selectedMockupTab === 'tote_bag' ? latestProductionJob.mockup_urls?.['tote'] : latestProductionJob.mockup_urls?.['tote_bag'])"
                            target="_blank"
                            :download="`${selectedMockupTab}_mockup.jpg`"
                            class="absolute bottom-2 right-2 rounded bg-white/90 hover:bg-white border border-zinc-200 p-1.5 text-zinc-700 shadow-xs text-[10px] font-mono flex items-center gap-1"
                          >
                            <Download class="h-3 w-3" />
                            <span>Save Mockup</span>
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Provenance & Regeneration Footer -->
                  <div class="pt-4 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-4 text-xs text-zinc-500">
                    <div class="flex items-center gap-4 text-[11px] font-mono">
                      <span>Source Asset: <code>{{ latestProductionJob.source_asset_id?.slice(0, 8) }}...</code></span>
                      <span>SHA256: <code>{{ latestProductionJob.qa_report?.checksum_sha256?.slice(0, 8) }}...</code></span>
                      <span>Pipeline: <code>image-pipeline@0.1.0</code></span>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      class="text-xs gap-1.5 ml-auto"
                      :disabled="isProductionLoading"
                      @click="() => triggerProduction(true)"
                    >
                      <RotateCw class="h-3.5 w-3.5" :class="{ 'animate-spin': isProductionLoading }" />
                      <span>Regenerate Master & Mockups</span>
                    </Button>
                  </div>
                </div>

                <!-- 4. Failed State -->
                <div v-if="workflow.state === 'PRODUCTION_FAILED' || (latestProductionJob?.status === 'FAILED' && workflow.state !== 'ARTWORK_APPROVED')" class="space-y-4">
                  <Alert variant="destructive">
                    <AlertCircle class="h-4 w-4" />
                    <AlertTitle>PNG Production Failed</AlertTitle>
                    <AlertDescription>
                      {{ latestProductionJob?.failure_message || 'An error occurred during production file processing.' }}
                    </AlertDescription>
                  </Alert>

                  <Button
                    variant="default"
                    size="sm"
                    class="gap-1.5"
                    :disabled="isProductionLoading"
                    @click="() => triggerProduction(true)"
                  >
                    <RotateCw class="h-3.5 w-3.5" :class="{ 'animate-spin': isProductionLoading }" />
                    <span>Retry PNG Production</span>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <!-- Original User Input Card -->
            <Card v-if="workflow && originalIdea" class="shadow-2xs bg-indigo-50/20 border-indigo-100">
              <CardHeader class="pb-3">
                <div class="flex items-center gap-2">
                  <Lightbulb class="h-4 w-4 text-indigo-600" />
                  <CardTitle class="text-base font-bold">
                    Original {{ workflow.idea_mode === 'hybrid' ? 'Theme / Direction' : 'Idea Brief' }}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-zinc-700">
                <div>
                  <span class="font-semibold text-zinc-500 block mb-1">Verbatim Wording:</span>
                  <p class="italic bg-white p-3 rounded-lg border border-zinc-200/80">"{{ originalIdea.original_text }}"</p>
                </div>
                <div class="space-y-1.5">
                  <div v-if="originalIdea.slogan">
                    <span class="font-semibold text-zinc-500">Slogan:</span>
                    <span class="ml-1 font-mono bg-white px-1.5 py-0.5 rounded border border-zinc-200">{{ originalIdea.slogan }}</span>
                  </div>
                  <div v-if="originalIdea.desired_style">
                    <span class="font-semibold text-zinc-500">Desired Style:</span>
                    <span class="ml-1">{{ originalIdea.desired_style }}</span>
                  </div>
                  <div v-if="originalIdea.audience">
                    <span class="font-semibold text-zinc-500">Audience:</span>
                    <span class="ml-1">{{ originalIdea.audience }}</span>
                  </div>
                  <div v-if="originalIdea.occasion">
                    <span class="font-semibold text-zinc-500">Occasion:</span>
                    <span class="ml-1">{{ originalIdea.occasion }}</span>
                  </div>
                  <div v-if="originalIdea.season">
                    <span class="font-semibold text-zinc-500">Season:</span>
                    <span class="ml-1">{{ originalIdea.season }}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Synthesised Product Concepts Header -->
            <div class="flex items-center justify-between">
              <h2 class="text-xl font-bold tracking-tight text-zinc-900">Synthesised Product Concepts</h2>
              <Badge variant="secondary" class="text-xs">
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
                <CardHeader class="pb-3">
                  <div class="flex items-start justify-between gap-4">
                    <div class="space-y-1">
                      <div class="flex items-center gap-2 flex-wrap">
                        <CardTitle class="text-lg font-bold">{{ concept.title }}</CardTitle>
                        <Badge v-if="concept.status?.toUpperCase() === 'APPROVED'" variant="success" class="text-[10px] px-2 py-0">
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
                      <span>{{ concept.score ? concept.score.toFixed(2) : 'N/A' }}</span>
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent class="space-y-4 text-xs text-zinc-600">
                  <p class="text-sm text-zinc-700 leading-relaxed">{{ concept.description }}</p>

                  <!-- Differentiation -->
                  <div class="rounded-lg bg-zinc-50 p-3 border border-zinc-100">
                    <span class="font-bold text-zinc-800 block mb-0.5">Differentiation Strategy:</span>
                    <p>{{ concept.differentiation }}</p>
                  </div>

                  <!-- Risk Alert -->
                  <div
                    v-if="concept.risk_level !== 'low'"
                    class="rounded-lg bg-rose-50 p-3 border border-rose-200 text-rose-900"
                  >
                    <span class="font-bold block">⚠️ IP Risk Level: {{ concept.risk_level.toUpperCase() }}</span>
                    <p class="mt-0.5 text-rose-700">{{ concept.risk_note }}</p>
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
                        @click="openReviseForm(concept.id)"
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

                <!-- Gate Actions -->
                <CardFooter
                  v-if="workflow.state === 'IDEA_REVIEW' && ['PROPOSED', 'SHORTLISTED'].includes(concept.status?.toUpperCase())"
                  class="flex justify-end gap-3 border-t border-zinc-100 pt-4"
                >
                  <Button
                    variant="outline"
                    size="sm"
                    class="text-rose-700 hover:bg-rose-50 hover:border-rose-200"
                    @click="handleDecideGate(concept.id, 'REJECTED')"
                  >
                    Reject Concept
                  </Button>
                  <Button
                    variant="success"
                    size="sm"
                    class="font-bold"
                    @click="handleDecideGate(concept.id, 'APPROVED')"
                  >
                    Approve This Concept
                  </Button>
                </CardFooter>
              </Card>
            </div>
          </div>

          <!-- Campaign Target Brief Sidebar (Right 1 Column) -->
          <div class="space-y-6">
            <Card class="shadow-2xs">
              <CardHeader class="pb-3">
                <CardTitle class="text-base font-bold">Campaign Target Brief</CardTitle>
              </CardHeader>
              <CardContent class="space-y-4 text-xs">
                <div>
                  <span class="text-zinc-400 block uppercase tracking-wider text-[10px]">Marketplace</span>
                  <span class="text-zinc-900 font-bold uppercase">{{ workflow.target_marketplace }}</span>
                </div>
                <div>
                  <span class="text-zinc-400 block uppercase tracking-wider text-[10px]">Target Country & Language</span>
                  <span class="text-zinc-900 font-bold uppercase">{{ workflow.target_country }} ({{ workflow.output_language }})</span>
                </div>
                <div>
                  <span class="text-zinc-400 block uppercase tracking-wider text-[10px]">Target Buyer</span>
                  <span class="text-zinc-900 font-medium">{{ workflow.target_buyer || 'Generic Market' }}</span>
                </div>
                <div>
                  <span class="text-zinc-400 block uppercase tracking-wider text-[10px] mb-1">Physical Products</span>
                  <div class="flex flex-wrap gap-1">
                    <Badge v-for="use in workflow.intended_product_uses" :key="use" variant="secondary" class="text-[10px]">
                      {{ use }}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Original User Wording Section -->
            <Card v-if="originalIdea" class="shadow-2xs">
              <CardHeader class="pb-3">
                <CardTitle class="text-base font-bold">Original Concept Wording</CardTitle>
              </CardHeader>
              <CardContent class="space-y-3 text-xs">
                <blockquote class="border-l-2 border-indigo-500 pl-3 italic text-zinc-600">
                  "{{ originalIdea.original_text }}"
                </blockquote>
                <div class="space-y-1 text-zinc-500">
                  <p v-if="originalIdea.desired_style">Style: {{ originalIdea.desired_style }}</p>
                  <p v-if="originalIdea.slogan">Typography: "{{ originalIdea.slogan }}"</p>
                  <p v-if="originalIdea.season">Season: {{ originalIdea.season }}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <!-- Revision Modal -->
      <Dialog :open="isEditingPrompt" max-width="xl" @close="isEditingPrompt = false">
        <DialogHeader>
          <DialogTitle>Revise Design Prompt</DialogTitle>
          <DialogDescription>
            Adjust the generation values. A new version will be appended to support clean trace audit logs.
          </DialogDescription>
        </DialogHeader>

        <Alert v-if="revisionError" variant="destructive" class="my-4">
          <AlertCircle class="h-4 w-4" />
          <AlertDescription>{{ revisionError }}</AlertDescription>
        </Alert>

        <form class="space-y-4 mt-4" @submit.prevent="submitRevision">
          <div class="space-y-1.5">
            <Label for="revise-positive" required>Positive Prompt</Label>
            <Textarea
              id="revise-positive"
              v-model="editPositivePrompt"
              required
              :rows="4"
            />
          </div>

          <div class="space-y-1.5">
            <Label for="revise-negative" required>Negative Prompt (Required)</Label>
            <Textarea
              id="revise-negative"
              v-model="editNegativePrompt"
              required
              :rows="2"
            />
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label for="revise-slogan">Exact Slogan</Label>
              <Input id="revise-slogan" v-model="editSlogan" />
            </div>
            <div class="space-y-1.5">
              <Label for="revise-typography">Typography Instructions</Label>
              <Input id="revise-typography" v-model="editTypography" />
            </div>
          </div>

          <div class="space-y-1.5">
            <Label for="revise-note" required>Reason for Change / Change Note</Label>
            <Input
              id="revise-note"
              v-model="editChangeNote"
              required
              placeholder="e.g. emphasising watercolor texture"
            />
          </div>

          <DialogFooter>
            <Button variant="outline" size="sm" @click="isEditingPrompt = false">
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              size="sm"
              :loading="isSubmittingRevision"
              class="font-bold"
            >
              <span>Apply Revision</span>
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      <!-- Refinement Modal -->
      <Dialog :open="showRefineModal" max-width="lg" @close="showRefineModal = false">
        <DialogHeader>
          <DialogTitle>Refine Artwork Candidate</DialogTitle>
          <DialogDescription>
            Submit an image-to-image refinement using this candidate as reference.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 mt-4">
          <div class="space-y-1.5">
            <Label for="refine-prompt" required>Refinement Instructions</Label>
            <Textarea
              id="refine-prompt"
              v-model="refinePrompt"
              :rows="4"
              placeholder="Describe how to adjust the design (e.g. 'Add a border around text, make colors more vibrant')"
            />
          </div>

          <div class="space-y-1.5">
            <Label for="refine-change-note" required>Change Note</Label>
            <Input
              id="refine-change-note"
              v-model="refineChangeNote"
              placeholder="Brief label for this revision (e.g. 'More vibrant colors')"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" @click="showRefineModal = false">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            :loading="isArtworkLoading"
            class="font-bold"
            @click="submitRefinement"
          >
            Submit Refinement
          </Button>
        </DialogFooter>
      </Dialog>
    </main>
  </div>
</template>
