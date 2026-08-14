<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  canDelete,
  isRunning,
  isStopped,
  needsOwner,
  stageLabel,
  useWorkflowControls
} from "~/composables/useWorkflowControls";

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
  provenance: Record<string, any>;
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

const artworkJobs = ref<ArtworkJob[]>([]);
const isArtworkLoading = ref(false);
const artworkError = ref<string | null>(null);
const artProvider = ref("recraft");
const artModel = ref("recraftv4_1");

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
  } catch (err) {
    pageError.value = "Failed to load workflow details. Please verify your connection.";
  } finally {
    if (!silent) isPageLoading.value = false;
  }
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
      quality: "standard"
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
    startPolling();
  } catch (err: any) {
    artworkError.value = err.data?.detail || "Failed to trigger artwork generation.";
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
      quality: "standard"
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/artwork/regenerate`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
    startPolling();
  } catch (err: any) {
    artworkError.value = err.data?.detail || "Failed to regenerate artwork.";
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
      change_note: refineChangeNote.value
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
  } catch (err: any) {
    artworkError.value = err.data?.detail || "Failed to submit refinement.";
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
      target_version: null
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/approvals`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
  } catch (err: any) {
    artworkError.value = err.data?.detail || "Failed to approve artwork candidate.";
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
      target_version: workflowVersion
    };

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${workflowId}/approvals`,
      { method: "POST", headers, body: payload, credentials: "include" }
    );
    await loadData();
  } catch (err: any) {
    artworkError.value = err.data?.detail || "Failed to reject artwork options.";
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
  } catch (err: any) {
    revisionError.value = err.data?.detail || "Failed to submit prompt revision.";
  } finally {
    isSubmittingRevision.value = false;
  }
}

const { controlError, pendingWorkflowId, controlWorkflow } = useWorkflowControls(
  apiBase,
  () => loadData()
);

/**
 * Deleting is two steps. It removes the campaign from the owner's list, so it
 * should not happen on a single mis-click next to Stop.
 */
const confirmingDelete = ref(false);

async function deleteCampaign(id: string): Promise<void> {
  stopPolling();
  if (await controlWorkflow(id, "delete")) {
    await router.push("/");
  } else {
    confirmingDelete.value = false;
  }
}

function startPolling(): void {
  stopPolling();
  pollInterval = setInterval(() => {
    const s = workflow.value?.state;
    if (s && isRunning(s)) {
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
  const s = workflow.value?.state;
  if (s && isRunning(s)) {
    startPolling();
  }
});

onBeforeUnmount(stopPolling);
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-6 py-12">
      <!-- Loading State -->
      <div v-if="isPageLoading" class="flex flex-col items-center justify-center py-24 text-slate-500 animate-pulse">
        <p class="text-lg">Fetching campaign details...</p>
      </div>

      <!-- Page Error -->
      <div v-else-if="pageError" class="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900" role="alert">
        <h2 class="text-lg font-bold mb-2">Error Loading Campaign</h2>
        <p class="mb-4">{{ pageError }}</p>
        <button type="button" class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700" @click="() => loadData()">
          Retry
        </button>
      </div>

      <!-- Workflow Detail Dashboard -->
      <div v-else-if="workflow" class="space-y-8">
        <!-- Campaign Header -->
        <header class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-slate-200 pb-6">
          <div>
            <div class="flex items-center gap-3">
              <NuxtLink to="/" class="text-sm font-medium text-indigo-600 hover:underline">← Campaigns</NuxtLink>
              <span class="text-slate-300">/</span>
              <span class="text-xs font-mono uppercase bg-slate-100 px-2 py-0.5 rounded text-slate-600">{{ workflow.idea_mode }}</span>
            </div>
            <h1 class="text-3xl font-extrabold text-slate-900 mt-2">{{ workflow.name }}</h1>
            <p class="text-sm text-slate-500 mt-1">ID: {{ workflow.id }}</p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-bold"
              :class="{
                'bg-slate-100 text-slate-800 border-slate-200': workflow.state === 'DRAFT' || workflow.state === 'CANCELLED',
                'bg-amber-100 text-amber-800 border-amber-200': isRunning(workflow.state),
                'bg-blue-100 text-blue-800 border-blue-200': needsOwner(workflow.state),
                'bg-green-100 text-green-800 border-green-200': workflow.state.endsWith('_APPROVED') || workflow.state === 'ETSY_DRAFT_CREATED',
                'bg-red-100 text-red-800 border-red-200': workflow.state.endsWith('_FAILED')
              }"
            >
              <span
                v-if="isRunning(workflow.state)"
                class="h-2 w-2 rounded-full bg-amber-600 motion-safe:animate-pulse"
                aria-hidden="true"
              />
              {{ stageLabel(workflow.state) }}
            </span>

            <!-- Same rule as the campaign list: stop only while work is
                 running, rerun only after it was stopped. -->
            <button
              v-if="isRunning(workflow.state)"
              type="button"
              :disabled="pendingWorkflowId === workflow.id"
              class="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700 transition-colors hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
              @click="controlWorkflow(workflow.id, 'cancel')"
            >
              <svg class="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" fill="currentColor" />
              </svg>
              Stop
            </button>
            <button
              v-if="isStopped(workflow.state)"
              type="button"
              :disabled="pendingWorkflowId === workflow.id"
              class="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-semibold text-indigo-700 transition-colors hover:bg-indigo-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
              @click="controlWorkflow(workflow.id, 'rerun')"
            >
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M20 11a8 8 0 1 0-.6 4" />
                <path d="M20 4v7h-7" />
              </svg>
              Rerun
            </button>

            <!-- Deleting is refused while a job holds the campaign, so the
                 button is only offered once nothing is in flight. -->
            <button
              v-if="canDelete(workflow.state) && !confirmingDelete"
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
              @click="confirmingDelete = true"
            >
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 7h16" />
                <path d="M10 11v6M14 11v6" />
                <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
                <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
              </svg>
              Delete
            </button>
            <span
              v-else-if="confirmingDelete"
              class="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-800"
            >
              Delete this campaign?
              <button
                type="button"
                :disabled="pendingWorkflowId === workflow.id"
                class="rounded-md bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
                @click="deleteCampaign(workflow.id)"
              >
                Delete
              </button>
              <button
                type="button"
                class="rounded-md px-2 py-1 text-xs font-semibold text-slate-600 underline hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
                @click="confirmingDelete = false"
              >
                Keep
              </button>
            </span>
          </div>
        </header>

        <div v-if="controlError" class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
          {{ controlError }}
        </div>

        <!-- A stopped campaign keeps its history but has nothing in flight;
             rerunning starts a fresh research run from the same brief. -->
        <section
          v-if="isStopped(workflow.state)"
          class="rounded-2xl border border-slate-200 bg-white p-8 text-center"
        >
          <h2 class="mb-1 text-xl font-bold text-slate-800">Campaign stopped</h2>
          <p class="mx-auto max-w-md text-sm text-slate-600">
            Nothing is running. Everything already gathered stays on the record — rerun to start a new research run from the same brief.
          </p>
        </section>

        <!-- Polling / Processing State -->
        <section
          v-if="workflow.state === 'RESEARCH_QUEUED' || workflow.state === 'RESEARCHING'"
          class="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-8 text-center"
        >
          <div class="h-10 w-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 class="text-xl font-bold text-slate-800 mb-1">AI Market Research in Progress</h2>
          <p class="text-sm text-slate-600 max-w-md mx-auto">
            Our background worker is analyzing seasonal demand on Etsy, matching keyword query angles, screening trademarks, and drafting structured prompts. This will automatically refresh.
          </p>
        </section>

        <!-- Failed State -->
        <section
          v-else-if="workflow.state === 'RESEARCH_FAILED'"
          class="rounded-2xl border border-red-200 bg-red-50 p-8 text-center"
        >
          <div class="text-4xl mb-3">⚠️</div>
          <h2 class="text-xl font-bold text-red-900 mb-1">Research Campaign Failed</h2>
          <p class="text-sm text-red-700 max-w-md mx-auto mb-4">
            Reason: {{ latestRun?.failure_reason || 'An unexpected worker error occurred.' }}
          </p>
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl bg-red-600 px-5 py-3 text-sm font-semibold text-white hover:bg-red-700 shadow"
            @click="startResearch"
          >
            Retry Campaign Research
          </button>
        </section>

        <!-- Artwork Polling / Processing State -->
        <section
          v-else-if="workflow.state === 'ART_QUEUED' || workflow.state === 'ART_GENERATION'"
          class="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-8 text-center"
        >
          <div class="h-10 w-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 class="text-xl font-bold text-slate-800 mb-1">Generating Artwork Candidates</h2>
          <p class="text-sm text-slate-600 max-w-md mx-auto">
            Our background worker is calling Recraft/Gemini to generate transparent-background PNG/SVG candidates matching the approved prompt. This will automatically refresh.
          </p>
        </section>

        <!-- Artwork Failed State -->
        <section
          v-else-if="workflow.state === 'ART_GENERATION_FAILED'"
          class="rounded-2xl border border-red-200 bg-red-50 p-8 text-center"
        >
          <div class="text-4xl mb-3">⚠️</div>
          <h2 class="text-xl font-bold text-red-900 mb-1">Artwork Generation Failed</h2>
          <p class="text-sm text-red-700 max-w-md mx-auto mb-4">
            Reason: {{ artworkJobs[0]?.failure_message || 'An unexpected worker error occurred.' }}
          </p>
          <div class="flex justify-center gap-3">
            <button
              type="button"
              class="inline-flex items-center justify-center rounded-xl bg-red-600 px-5 py-3 text-sm font-semibold text-white hover:bg-red-700 shadow"
              @click="() => startArtwork()"
            >
              Retry Generation
            </button>
            <button
              type="button"
              class="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              @click="() => regenerateArtwork()"
            >
              Reconfigure
            </button>
          </div>
        </section>

        <!-- Main Workspace -->
        <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <!-- Concepts & Approvals (Left 2 Columns) -->
          <div class="lg:col-span-2 space-y-8">
            <!-- Trigger Artwork Generation Panel -->
            <div v-if="workflow.state === 'IDEA_APPROVED'" class="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-6 shadow-sm">
              <h3 class="text-lg font-bold text-slate-900 mb-2">🎨 Step 2: Trigger Artwork Generation</h3>
              <p class="text-sm text-slate-600 mb-4">
                Now that your concept is approved, select your preferred generation parameters below.
              </p>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Image Provider</label>
                  <select v-model="artProvider" class="w-full rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500">
                    <option value="recraft">Recraft V4.1 (Vector & Illustration)</option>
                    <option value="gemini">Google Gemini (Photo & Creative)</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Model Profile</label>
                  <select v-model="artModel" class="w-full rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500">
                    <option v-if="artProvider === 'recraft'" value="recraftv4_1">Recraft V4.1 (Standard)</option>
                    <option v-if="artProvider === 'recraft'" value="recraftv4_1_pro">Recraft V4.1 Pro (Premium, 1 Candidate)</option>
                    <option v-if="artProvider === 'gemini'" value="gemini-3.1-flash-image">Gemini 3.1 Flash Image (Standard)</option>
                  </select>
                </div>
              </div>
              <div v-if="artworkError" class="text-sm text-red-600 mb-4 bg-red-50 border border-red-100 p-3 rounded-lg">
                {{ artworkError }}
              </div>
              <div class="flex items-center justify-between gap-4 border-t border-slate-100 pt-4">
                <span class="text-xs text-slate-500 font-medium">Estimated cost: $0.00 (Fake Adapter)</span>
                <button
                  type="button"
                  :disabled="isArtworkLoading"
                  class="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                  @click="() => startArtwork()"
                >
                  {{ isArtworkLoading ? 'Enqueuing...' : 'Generate Artwork Candidates' }}
                </button>
              </div>
            </div>

            <!-- Candidate Gallery -->
            <div v-if="workflow.state === 'ART_REVIEW' || workflow.state === 'ARTWORK_APPROVED'" class="space-y-6">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <h3 class="text-2xl font-extrabold text-slate-900">Generated Artwork Candidates</h3>
                  <p class="text-sm text-slate-500">Review and select the winning candidate for production.</p>
                </div>
                <button
                  v-if="workflow.state === 'ART_REVIEW'"
                  type="button"
                  class="text-xs font-semibold text-red-600 hover:text-red-800 underline"
                  @click="() => workflow && rejectArtwork(artworkJobs[0]?.id, workflow.version)"
                >
                  Reject All Options
                </button>
              </div>

              <div v-if="artworkError" class="text-sm text-red-600 bg-red-50 border border-red-100 p-3 rounded-lg">
                {{ artworkError }}
              </div>

              <!-- Artwork Candidates Grid -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div
                  v-for="(asset, idx) in artworkJobs[0]?.assets"
                  :key="asset.id"
                  class="group relative rounded-2xl border bg-white overflow-hidden shadow-sm hover:shadow transition-shadow duration-150"
                  :class="workflow.state === 'ARTWORK_APPROVED' && asset.derived_from_id === null ? 'border-green-500 ring-2 ring-green-500/20' : 'border-slate-200'"
                >
                  <!-- Candidate Thumbnail -->
                  <div class="aspect-square bg-slate-100 relative flex items-center justify-center overflow-hidden">
                    <img
                      v-if="asset.url"
                      :src="asset.url"
                      alt="Candidate Preview"
                      class="object-contain w-full h-full max-h-[350px]"
                    />
                    <div v-else class="text-slate-400 text-sm">Preview Loading...</div>
                    <span class="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-xs text-white text-xs font-mono px-2 py-1 rounded">
                      Candidate {{ idx + 1 }}
                    </span>
                  </div>

                  <!-- Candidate Details & Action Footer -->
                  <div class="p-4 border-t border-slate-100 bg-slate-50/50">
                    <div class="flex items-center justify-between text-xs text-slate-500 mb-3">
                      <span>{{ asset.width }}x{{ asset.height }} | {{ (asset.byte_size / 1024).toFixed(1) }} KB</span>
                      <span class="capitalize">{{ asset.mime_type.split('/')[1] }}</span>
                    </div>

                    <div v-if="workflow.state === 'ART_REVIEW'" class="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        class="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        @click="() => openRefineModalForm(asset.id)"
                      >
                        Refine Option
                      </button>
                      <button
                        type="button"
                        class="inline-flex items-center justify-center rounded-lg bg-green-600 px-3 py-2 text-xs font-bold text-white hover:bg-green-700"
                        @click="() => approveArtwork(asset.id)"
                      >
                        Approve Candidate
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Regeneration button at bottom -->
              <div v-if="workflow.state === 'ART_REVIEW'" class="rounded-2xl border border-dashed border-slate-200 p-6 text-center">
                <p class="text-sm text-slate-500 mb-3">Not satisfied with any of these candidates?</p>
                <button
                  type="button"
                  class="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 shadow-sm"
                  @click="() => regenerateArtwork()"
                >
                  Regenerate All Options
                </button>
              </div>
            </div>

            <h2 class="text-2xl font-bold text-slate-800">Synthesised Product Concepts</h2>

            <div v-if="concepts.length === 0" class="rounded-xl border border-slate-200 bg-white p-8 text-center">
              <p class="text-slate-500">No concepts generated for this workflow yet.</p>
            </div>

            <!-- Concept Cards -->
            <div v-else class="space-y-6">
              <article
                v-for="concept in concepts"
                :key="concept.id"
                class="rounded-2xl border bg-white p-6 shadow-sm hover:shadow transition-shadow duration-150"
                :class="concept.status === 'APPROVED' ? 'border-green-500 ring-1 ring-green-500/20' : 'border-slate-200'"
              >
                <!-- Title & Score Header -->
                <header class="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 class="text-xl font-extrabold text-slate-900">{{ concept.title }}</h3>
                    <p class="text-xs text-slate-500 mt-0.5">Origin: {{ concept.origin }} | Status: {{ concept.status }}</p>
                  </div>
                  <div class="text-right">
                    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold text-sm">
                      ★ {{ concept.score ? concept.score.toFixed(2) : 'N/A' }}
                    </span>
                  </div>
                </header>

                <p class="text-slate-600 text-sm mb-4">{{ concept.description }}</p>

                <!-- Differentiation -->
                <div class="mb-4 bg-slate-50 p-3 rounded-lg text-sm border border-slate-100">
                  <span class="font-bold text-slate-700 block">Differentiation Strategy:</span>
                  <p class="text-slate-600 mt-0.5">{{ concept.differentiation }}</p>
                </div>

                <!-- Risk Alerts -->
                <div
                  v-if="concept.risk_level !== 'low'"
                  class="mb-4 rounded-lg bg-red-50 p-3 border border-red-100 text-sm text-red-900"
                >
                  <span class="font-bold block">⚠️ IP Risk Level: {{ concept.risk_level.toUpperCase() }}</span>
                  <p class="text-xs text-red-700 mt-0.5">{{ concept.risk_note }}</p>
                </div>

                <!-- Score Breakdown -->
                <div class="mb-6 grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs border-t border-slate-100 pt-4">
                  <div v-for="(val, key) in concept.score_breakdown" :key="key" class="bg-slate-50/50 p-2 rounded border border-slate-100">
                    <span class="text-slate-500 uppercase tracking-wider block text-[10px]">{{ key.replace('_', ' ') }}</span>
                    <span class="text-slate-800 font-bold text-sm">{{ val }} / 5</span>
                  </div>
                </div>

                <!-- Latest Prompt Version details -->
                <div class="bg-indigo-50/25 p-4 rounded-xl border border-indigo-100/50 mb-6 text-sm">
                  <div class="flex justify-between items-center mb-2 border-b border-indigo-100/50 pb-2">
                    <span class="font-bold text-indigo-900">Active Design Prompt (v{{ concept.prompts[concept.prompts.length - 1]?.version || 1 }})</span>
                    <button
                      v-if="workflow.state === 'IDEA_REVIEW' && concept.status === 'PROPOSED'"
                      type="button"
                      class="text-indigo-600 hover:text-indigo-900 font-bold text-xs underline"
                      @click="openReviseForm(concept.id)"
                    >
                      Edit Prompt
                    </button>
                  </div>
                  <div class="space-y-2">
                    <p><span class="font-semibold text-slate-700">Positive:</span> {{ concept.prompts[concept.prompts.length - 1]?.positive_prompt }}</p>
                    <p><span class="font-semibold text-slate-700">Negative:</span> {{ concept.prompts[concept.prompts.length - 1]?.negative_prompt }}</p>
                    <p v-if="concept.prompts[concept.prompts.length - 1]?.exact_slogan">
                      <span class="font-semibold text-slate-700">Typography Slogan:</span>
                      <code class="bg-indigo-50 text-indigo-800 px-1 py-0.5 rounded font-bold">
                        "{{ concept.prompts[concept.prompts.length - 1]?.exact_slogan }}"
                      </code>
                    </p>
                  </div>
                </div>

                <!-- Gate Actions -->
                <footer v-if="workflow.state === 'IDEA_REVIEW' && concept.status === 'PROPOSED'" class="flex justify-end gap-3 border-t border-slate-100 pt-4">
                  <button
                    type="button"
                    class="inline-flex items-center justify-center rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
                    @click="handleDecideGate(concept.id, 'REJECTED')"
                  >
                    Reject Concept
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center justify-center rounded-lg bg-green-600 px-5 py-2 text-sm font-bold text-white hover:bg-green-700"
                    @click="handleDecideGate(concept.id, 'APPROVED')"
                  >
                    Approve Concept (Gate 1)
                  </button>
                </footer>
              </article>
            </div>
          </div>

          <!-- Campaign Context / Original brief (Right 1 Column) -->
          <div class="space-y-8">
            <section class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 class="text-xl font-bold text-slate-800 mb-4">Campaign Target Brief</h2>
              <dl class="space-y-4 text-sm">
                <div>
                  <dt class="text-slate-500 font-medium">Marketplace</dt>
                  <dd class="text-slate-800 font-semibold uppercase">{{ workflow.target_marketplace }}</dd>
                </div>
                <div>
                  <dt class="text-slate-500 font-medium">Target Country & Lang</dt>
                  <dd class="text-slate-800 font-semibold uppercase">{{ workflow.target_country }} ({{ workflow.output_language }})</dd>
                </div>
                <div>
                  <dt class="text-slate-500 font-medium">Target Buyer</dt>
                  <dd class="text-slate-800 font-semibold">{{ workflow.target_buyer || 'Generic Market' }}</dd>
                </div>
                <div>
                  <dt class="text-slate-500 font-medium">Physical Use-cases</dt>
                  <dd class="text-slate-800 flex flex-wrap gap-1 mt-1">
                    <span v-for="use in workflow.intended_product_uses" :key="use" class="bg-slate-100 px-2 py-0.5 rounded text-xs text-slate-600">
                      {{ use }}
                    </span>
                  </dd>
                </div>
              </dl>
            </section>

            <!-- Original User Wording comparison -->
            <section v-if="originalIdea" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 class="text-xl font-bold text-slate-800 mb-4">Original Concept Wording</h2>
              <blockquote class="border-l-4 border-indigo-500 pl-4 italic text-slate-600 text-sm mb-4">
                "{{ originalIdea.original_text }}"
              </blockquote>
              <dl class="space-y-2 text-xs text-slate-500">
                <li v-if="originalIdea.desired_style">Style request: {{ originalIdea.desired_style }}</li>
                <li v-if="originalIdea.slogan">Typography request: "{{ originalIdea.slogan }}"</li>
                <li v-if="originalIdea.season">Season request: {{ originalIdea.season }}</li>
              </dl>
            </section>
          </div>
        </div>
      </div>

      <!-- Revision Modal -->
      <div v-if="isEditingPrompt" class="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-6 z-50 animate-fade-in">
        <div class="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
          <header>
            <h3 class="text-xl font-extrabold text-slate-900">Revise Design Prompt</h3>
            <p class="text-sm text-slate-500">Adjust the generation values. A new version will be appended to support clean artwork trace audit logs.</p>
          </header>

          <div v-if="revisionError" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {{ revisionError }}
          </div>

          <form @submit.prevent="submitRevision" class="space-y-4">
            <div>
              <label for="revise-positive" class="block text-sm font-semibold text-slate-700">Positive Prompt</label>
              <textarea
                id="revise-positive"
                v-model="editPositivePrompt"
                required
                rows="4"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              ></textarea>
            </div>

            <div>
              <label for="revise-negative" class="block text-sm font-semibold text-slate-700">Negative Prompt (Required)</label>
              <textarea
                id="revise-negative"
                v-model="editNegativePrompt"
                required
                rows="2"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              ></textarea>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label for="revise-slogan" class="block text-sm font-semibold text-slate-700">Exact Slogan</label>
                <input
                  id="revise-slogan"
                  v-model="editSlogan"
                  type="text"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
              <div>
                <label for="revise-typography" class="block text-sm font-semibold text-slate-700">Typography Instructions</label>
                <input
                  id="revise-typography"
                  v-model="editTypography"
                  type="text"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
            </div>

            <div>
              <label for="revise-note" class="block text-sm font-semibold text-slate-700">Reason for Change / Change Note</label>
              <input
                id="revise-note"
                v-model="editChangeNote"
                required
                type="text"
                placeholder="e.g. emphasising oil paint texture"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              />
            </div>

            <footer class="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                class="inline-flex justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
                @click="isEditingPrompt = false"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="isSubmittingRevision"
                class="inline-flex justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
              >
                {{ isSubmittingRevision ? 'Saving...' : 'Apply Revision' }}
              </button>
            </footer>
          </form>
        </div>
      </div>

      <!-- Refinement Modal -->
      <div v-if="showRefineModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-6 z-50 animate-fade-in">
        <div class="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
          <div>
            <h2 class="text-2xl font-bold text-slate-900">Refine Artwork Candidate</h2>
            <p class="text-sm text-slate-500 mt-1">This will submit an image-to-image request using Gemini using this candidate as reference.</p>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-bold text-slate-700 mb-1">Refinement Instructions</label>
              <textarea
                v-model="refinePrompt"
                rows="4"
                placeholder="Describe how to adjust the design (e.g. 'Add a border around the text, make the colors more vibrant')"
                class="w-full rounded-xl border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500"
              ></textarea>
            </div>

            <div>
              <label class="block text-sm font-bold text-slate-700 mb-1">Change Note</label>
              <input
                v-model="refineChangeNote"
                type="text"
                placeholder="Brief label for this revision (e.g. 'More vibrant colors')"
                class="w-full rounded-xl border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <div class="flex justify-end gap-3 border-t border-slate-100 pt-4">
            <button
              type="button"
              class="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              @click="() => { showRefineModal = false; }"
            >
              Cancel
            </button>
            <button
              type="button"
              class="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-5 py-2 text-sm font-bold text-white hover:bg-indigo-700"
              @click="submitRefinement"
            >
              Submit Refinement
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.animate-fade-in {
  animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
