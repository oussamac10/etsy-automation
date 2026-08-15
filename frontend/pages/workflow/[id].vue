<script setup lang="ts">
/* global $fetch */
import { ref, onMounted, onBeforeUnmount, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  isRunning,
  stageLabel,
  useWorkflowControls,
} from "~/composables/useWorkflowControls";

import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

import WorkflowHeader from "~/components/workflow/WorkflowHeader.vue";
import WorkflowStageNav from "~/components/workflow/WorkflowStageNav.vue";
import WorkflowOverviewTab from "~/components/workflow/WorkflowOverviewTab.vue";
import WorkflowConceptsTab from "~/components/workflow/WorkflowConceptsTab.vue";
import WorkflowArtworkTab from "~/components/workflow/WorkflowArtworkTab.vue";
import WorkflowProductionTab from "~/components/workflow/WorkflowProductionTab.vue";
import WorkflowPromptModal from "~/components/workflow/WorkflowPromptModal.vue";
import WorkflowRefineModal from "~/components/workflow/WorkflowRefineModal.vue";

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

// Active Tab navigation state
const activeTab = ref<string>((route.query?.tab as string) || "overview");

watch(
  () => route.query?.tab,
  (newTab) => {
    if (newTab && typeof newTab === "string") {
      activeTab.value = newTab;
    }
  }
);

function setActiveTab(tab: string) {
  activeTab.value = tab;
  if (router?.replace) {
    router.replace({ query: { ...(route.query || {}), tab } });
  }
}

// Artwork & Production state
const artworkJobs = ref<ArtworkJob[]>([]);
const isArtworkLoading = ref(false);
const artworkError = ref<string | null>(null);

const latestProductionJob = ref<ProductionJob | null>(null);
const isProductionLoading = ref(false);
const productionError = ref<string | null>(null);
const selectedCandidateId = ref<string | null>(null);

const chosenCandidateId = computed(() => {
  if (selectedCandidateId.value) return selectedCandidateId.value;
  if (latestProductionJob.value?.source_asset_id) return latestProductionJob.value.source_asset_id;
  const firstAsset = artworkJobs.value[0]?.assets?.[0];
  return firstAsset ? firstAsset.id : null;
});

const approvedConcept = computed(() => {
  return concepts.value.find((c) => c.status?.toUpperCase() === "APPROVED");
});

// Modals State
const selectedConceptId = ref<string | null>(null);
const isEditingPrompt = ref(false);
const editPositivePrompt = ref("");
const editNegativePrompt = ref("");
const editSlogan = ref("");
const editTypography = ref("");
const editChangeNote = ref("");
const isSubmittingRevision = ref(false);
const revisionError = ref<string | null>(null);

const showRefineModal = ref(false);
const refinePrompt = ref("");
const refineChangeNote = ref("");
const refineAssetId = ref<string | null>(null);

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

    // Initial intelligent tab selection if not explicitly set in URL query
    if (!route.query?.tab && !silent) {
      if (wf.state === "ART_REVIEW" || wf.state === "ART_GENERATION" || wf.state === "ART_QUEUED" || wf.state === "IDEA_APPROVED") {
        activeTab.value = "artwork";
      } else if (wf.state === "ARTWORK_APPROVED" || wf.state === "PRODUCTION" || wf.state === "PRODUCTION_FAILED" || latestProductionJob.value?.status === "SUCCEEDED") {
        activeTab.value = "production";
      } else if (wf.state === "IDEA_REVIEW" || wf.state === "RESEARCHING" || wf.state === "RESEARCH_QUEUED") {
        activeTab.value = "concepts";
      } else {
        activeTab.value = "overview";
      }
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
  setActiveTab("production");
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
    if (decision === "APPROVED") {
      setActiveTab("artwork");
    }
  } catch {
    pageError.value = "Failed to submit decision.";
  }
}

async function startArtwork(provider = "recraft", model = "recraftv4_1"): Promise<void> {
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      provider,
      provider_model: model,
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

async function regenerateArtwork(provider = "recraft", model = "recraftv4_1"): Promise<void> {
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const payload = {
      provider,
      provider_model: model,
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

async function submitRefinement(payload: { prompt: string; change_note: string }): Promise<void> {
  if (!refineAssetId.value) return;
  isArtworkLoading.value = true;
  artworkError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const body = {
      candidate_asset_id: refineAssetId.value,
      positive_prompt: payload.prompt,
      change_note: payload.change_note,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork/refine`,
      { method: "POST", headers, body, credentials: "include" }
    );
    showRefineModal.value = false;
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
    selectedCandidateId.value = assetId;
    await loadData();
    setActiveTab("production");
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

async function submitRevision(payload: {
  positive_prompt: string;
  negative_prompt: string;
  exact_slogan: string;
  typography_instructions: string;
  change_note: string;
}): Promise<void> {
  if (!selectedConceptId.value) return;
  isSubmittingRevision.value = true;
  revisionError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const body = {
      positive_prompt: payload.positive_prompt,
      negative_prompt: payload.negative_prompt,
      exact_slogan: payload.exact_slogan || null,
      typography_instructions: payload.typography_instructions || null,
      change_note: payload.change_note,
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/concepts/${selectedConceptId.value}/revise`,
      { method: "POST", headers, body, credentials: "include" }
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

async function handleWorkflowControl(action: string, options?: Record<string, unknown>): Promise<void> {
  if (action === "delete") {
    stopPolling();
    if (await controlWorkflow(workflowId, "delete")) {
      await router.push("/");
    }
  } else if (action === "cancel") {
    await controlWorkflow(workflowId, "cancel");
  } else if (action === "rerun") {
    await controlWorkflow(workflowId, "rerun", options);
    startPolling();
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

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Loading State -->
      <div v-if="isPageLoading" class="flex flex-col items-center justify-center py-28 text-zinc-400 gap-3">
        <Icon name="lucide:loader-circle" class="size-8 animate-spin text-indigo-600" aria-hidden="true" />
        <p class="text-sm font-medium">Fetching campaign details...</p>
      </div>

      <!-- Page Error -->
      <Alert v-else-if="pageError" variant="destructive" class="mb-8">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertTitle>Error Loading Campaign</AlertTitle>
        <AlertDescription class="flex items-center justify-between mt-2">
          <span>{{ pageError }}</span>
          <Button variant="outline" size="sm" class="h-8 text-xs cursor-pointer" @click="() => loadData()">
            Retry
          </Button>
        </AlertDescription>
      </Alert>

      <!-- Main Workspace Layout -->
      <div v-else-if="workflow" class="space-y-6">
        <!-- 1. Header with Workflow Controls -->
        <WorkflowHeader
          :workflow="workflow"
          :latest-production-job="latestProductionJob"
          :is-workflow-running="isWorkflowRunning"
          :display-stage-label="displayStageLabel"
          :pending-workflow-id="pendingWorkflowId"
          :control-error="controlError"
          @control="handleWorkflowControl"
        />

        <!-- 2. Stage Navigation Bar (Overview, Concepts, Artwork, Production) -->
        <WorkflowStageNav
          :active-tab="activeTab"
          :workflow-state="workflow.state"
          :concepts-count="concepts.length"
          :candidates-count="artworkJobs[0]?.assets?.length || 0"
          :production-status="latestProductionJob?.status"
          @update:active-tab="setActiveTab"
        />

        <!-- 3. Active Tab View -->
        <transition mode="out-in" enter-active-class="transition duration-150 ease-out" enter-from-class="opacity-0 translate-y-1" enter-to-class="opacity-100 translate-y-0">
          <div :key="activeTab">
            <!-- Tab: Overview -->
            <WorkflowOverviewTab
              v-if="activeTab === 'overview'"
              :workflow="workflow"
              :original-idea="originalIdea"
              :latest-run="latestRun"
              :latest-production-job="latestProductionJob"
              :pending-workflow-id="pendingWorkflowId"
              @control="handleWorkflowControl"
              @navigate="setActiveTab"
            />

            <!-- Tab: Concepts & Research -->
            <WorkflowConceptsTab
              v-else-if="activeTab === 'concepts'"
              :workflow="workflow"
              :concepts="concepts"
              :latest-run="latestRun"
              :approved-concept="approvedConcept"
              @start-research="startResearch"
              @decide-gate="handleDecideGate"
              @edit-prompt="openReviseForm"
            />

            <!-- Tab: Artwork Studio -->
            <WorkflowArtworkTab
              v-else-if="activeTab === 'artwork'"
              :workflow="workflow"
              :approved-concept="approvedConcept"
              :artwork-jobs="artworkJobs"
              :chosen-candidate-id="chosenCandidateId"
              :is-artwork-loading="isArtworkLoading"
              :artwork-error="artworkError"
              :is-production-loading="isProductionLoading"
              :latest-production-job="latestProductionJob"
              @generate="startArtwork"
              @regenerate="regenerateArtwork"
              @refine="openRefineModalForm"
              @approve="approveArtwork"
              @reject-all="rejectArtwork"
              @switch-candidate="switchCandidateAndProduce"
              @select-candidate="(id) => (selectedCandidateId = id)"
            />

            <!-- Tab: Production & Mockups -->
            <WorkflowProductionTab
              v-else-if="activeTab === 'production'"
              :workflow="workflow"
              :approved-concept="approvedConcept"
              :latest-production-job="latestProductionJob"
              :is-production-loading="isProductionLoading"
              :production-error="productionError"
              @trigger-production="triggerProduction"
            />
          </div>
        </transition>
      </div>

      <!-- Modals -->
      <WorkflowPromptModal
        :open="isEditingPrompt"
        :positive-prompt="editPositivePrompt"
        :negative-prompt="editNegativePrompt"
        :slogan="editSlogan"
        :typography="editTypography"
        :change-note="editChangeNote"
        :is-submitting="isSubmittingRevision"
        :error="revisionError"
        @close="isEditingPrompt = false"
        @submit="submitRevision"
      />

      <WorkflowRefineModal
        :open="showRefineModal"
        :prompt="refinePrompt"
        :change-note="refineChangeNote"
        :is-loading="isArtworkLoading"
        @close="showRefineModal = false"
        @submit="submitRefinement"
      />
    </main>
  </div>
</template>
