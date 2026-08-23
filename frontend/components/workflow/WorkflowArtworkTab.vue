<script setup lang="ts">
import { ref, watch, computed } from "vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Label from "~/components/ui/Label.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import { sanitizeUrl } from "~/utils/sanitize";

interface DesignPrompt {
  id: string;
  version: number;
  positive_prompt: string;
  negative_prompt: string;
  typography_instructions: string | null;
  exact_slogan: string | null;
}

interface Concept {
  id: string;
  title: string;
  description: string;
  prompts: DesignPrompt[];
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

interface Workflow {
  id: string;
  state: string;
  version: number;
}

import type { ProductionJob } from "~/types/production";

const props = defineProps<{
  workflow: Workflow;
  approvedConcept?: Concept;
  artworkJobs: ArtworkJob[];
  chosenCandidateId: string | null;
  isArtworkLoading: boolean;
  artworkError: string | null;
  isProductionLoading: boolean;
  latestProductionJob: ProductionJob | null;
}>();

const emit = defineEmits<{
  (e: "generate", provider: string, model: string): void;
  (e: "regenerate", provider?: string, model?: string): void;
  (e: "refine", assetId: string): void;
  (e: "approve", assetId: string): void;
  (e: "rejectAll", jobId: string, version: number): void;
  (e: "switchCandidate", assetId: string): void;
  (e: "selectCandidate", assetId: string): void;
}>();

const artProvider = ref("recraft");
const artModel = ref("recraftv4_1");

watch(artProvider, (newVal) => {
  if (newVal === "recraft") {
    artModel.value = "recraftv4_1";
  } else {
    artModel.value = "gemini-3.1-flash-image";
  }
});

const relevantJobs = computed(() => {
  const currentConcept = props.approvedConcept;
  if (!currentConcept) return props.artworkJobs;
  return props.artworkJobs.filter((j) => j.concept_id === currentConcept.id);
});

const latestRelevantJob = computed(() => relevantJobs.value[0]);

const isJobInFlight = computed(() => {
  if (props.isArtworkLoading) return true;
  if (["ART_QUEUED", "ART_GENERATION"].includes(props.workflow.state)) return true;
  const latestJob = latestRelevantJob.value;
  if (!latestJob) return false;
  const status = latestJob.status?.toLowerCase();
  return ["queued", "running", "processing", "generating", "refining"].includes(status);
});

const isJobFailed = computed(() => {
  if (props.workflow.state === "ART_GENERATION_FAILED") return true;
  const latestJob = latestRelevantJob.value;
  return latestJob?.status?.toLowerCase() === "failed";
});

const currentAssets = computed(() => {
  const assets: Asset[] = [];
  const seen = new Set<string>();
  for (const job of relevantJobs.value) {
    if (job.assets) {
      for (const a of job.assets) {
        if (!seen.has(a.id)) {
          seen.add(a.id);
          assets.push(a);
        }
      }
    }
  }
  return assets;
});

function getAssetJob(assetId: string): ArtworkJob | undefined {
  return relevantJobs.value.find((j) => j.assets?.some((a) => a.id === assetId));
}

function isAssetRefined(assetId?: string | null): boolean {
  if (!assetId) return false;
  const asset = currentAssets.value.find((a) => a.id === assetId);
  const prov = asset?.provenance as Record<string, unknown> | undefined;
  if (prov?.operation === "refinement" || Boolean(asset?.derived_from_id)) return true;
  const job = getAssetJob(assetId);
  if (!job) return false;
  return (
    job.provider === "gemini" ||
    Boolean(job.provider_model?.includes("v3")) ||
    Boolean(job.provider_model?.includes("recraftv3"))
  );
}

const latestFailureMessage = computed(() => {
  return (
    latestRelevantJob.value?.failure_message ||
    props.artworkError ||
    "An unexpected error occurred during artwork generation."
  );
});

const selectedCandidateId = ref<string | null>(props.chosenCandidateId);

watch(
  () => props.chosenCandidateId,
  (newVal) => {
    if (!selectedCandidateId.value || selectedCandidateId.value === props.chosenCandidateId) {
      selectedCandidateId.value = newVal;
    }
  },
  { immediate: true }
);

function selectCandidate(assetId: string): void {
  selectedCandidateId.value = assetId;
  emit("selectCandidate", assetId);
}

function getSelectedAsset(): Asset | undefined {
  return currentAssets.value.find((a) => a.id === selectedCandidateId.value);
}

function getSelectedAssetIndex(): number {
  return currentAssets.value.findIndex((a) => a.id === selectedCandidateId.value);
}

// Preview Modal State
const previewingAsset = ref<Asset | null>(null);
const previewBg = ref<"checkerboard" | "white" | "dark">("checkerboard");

function openPreview(asset: Asset): void {
  previewingAsset.value = asset;
  selectedCandidateId.value = asset.id;
}

function getPreviewAssetIndex(): number {
  if (!previewingAsset.value) return 0;
  return currentAssets.value.findIndex((a) => a.id === previewingAsset.value?.id);
}

function navigatePreview(dir: -1 | 1): void {
  if (!currentAssets.value.length) return;
  const currentIdx = getPreviewAssetIndex();
  const nextIdx = currentIdx + dir;
  if (nextIdx >= 0 && nextIdx < currentAssets.value.length) {
    previewingAsset.value = currentAssets.value[nextIdx];
    selectedCandidateId.value = currentAssets.value[nextIdx].id;
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  if (!previewingAsset.value) return;
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    navigatePreview(-1);
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    navigatePreview(1);
  } else if (e.key === "Escape") {
    previewingAsset.value = null;
  }
}

watch(previewingAsset, (val) => {
  if (typeof window === "undefined") return;
  if (val) {
    window.addEventListener("keydown", handleKeyDown);
  } else {
    window.removeEventListener("keydown", handleKeyDown);
  }
});

import { onUnmounted } from "vue";
onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", handleKeyDown);
  }
});
</script>

<template>
  <div class="space-y-6">
    <!-- Phase 6 Card -->
    <Card class="shadow-2xs">
      <CardHeader class="pb-4 border-b border-border bg-secondary/30">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div class="flex items-start sm:items-center gap-3 min-w-0">
            <div class="flex size-9 sm:size-10 items-center justify-center rounded-xl bg-secondary text-primary border border-border shrink-0">
              <Icon name="lucide:image" class="size-5 shrink-0 text-primary" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <CardTitle class="text-lg font-bold">Artwork Generation & Approval</CardTitle>
              <CardDescription class="text-xs text-muted-foreground leading-relaxed">
                Select AI generator and approve the preferred candidate design before producing print files.
              </CardDescription>
            </div>
          </div>
          <Badge
            v-if="workflow.state === 'ARTWORK_APPROVED' || latestProductionJob !== null"
            variant="success"
            class="gap-1 px-3 py-1 font-semibold inline-flex items-center shrink-0 self-start sm:self-auto"
          >
            <Icon name="lucide:check" class="size-3 shrink-0" aria-hidden="true" />
            <span>Artwork Approved</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent class="space-y-6 p-6">
        <!-- Selected Concept Info -->
        <div v-if="approvedConcept" class="rounded-xl border border-border bg-secondary/30 p-4 text-sm space-y-3">
          <div>
            <span class="text-[10px] font-bold uppercase tracking-wider text-primary">Locked Concept</span>
            <h4 class="text-base font-bold text-foreground">{{ approvedConcept.title }}</h4>
            <p class="text-xs text-secondary-foreground mt-0.5">{{ approvedConcept.description }}</p>
          </div>

          <div class="rounded-lg border border-border bg-white p-3 space-y-1 text-xs font-mono">
            <p>
              <span class="font-bold text-muted-foreground">Base Prompt:</span>
              {{ approvedConcept.prompts[0]?.positive_prompt }}
            </p>
            <p>
              <span class="font-bold text-muted-foreground">Negative:</span>
              {{ approvedConcept.prompts[0]?.negative_prompt }}
            </p>
            <p v-if="approvedConcept.prompts[0]?.exact_slogan">
              <span class="font-bold text-muted-foreground">Slogan:</span>
              "{{ approvedConcept.prompts[0]?.exact_slogan }}"
            </p>
          </div>
        </div>

        <!-- Inner state 1: Gate 1 approved + ready to generate artwork (first time) -->
        <div v-if="workflow.state === 'IDEA_APPROVED' && !currentAssets.length && !isJobInFlight && !isJobFailed" class="space-y-4">
          <div class="rounded-xl bg-secondary/40 border border-border p-4 text-xs text-foreground font-medium">
            Your concept is approved. Generate artwork to continue.
          </div>

          <!-- Parameters selection -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <Label for="image-provider">Image Provider</Label>
              <select
                id="image-provider"
                v-model="artProvider"
                class="flex h-9 w-full rounded-md border border-border bg-white px-3 py-1 text-sm shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
              >
                <option value="recraft">Recraft V4.1 (Vector & Illustration)</option>
                <option value="gemini">Google Gemini (Photo & Creative)</option>
              </select>
            </div>
            <div class="space-y-1.5">
              <Label for="image-model">Model</Label>
              <input
                id="image-model"
                v-model="artModel"
                readonly
                disabled
                class="flex h-9 w-full rounded-md border border-border bg-secondary/60 px-3 py-1 text-sm text-muted-foreground shadow-2xs"
              >
            </div>
          </div>

          <Button
            variant="default"
            size="lg"
            class="w-full text-base font-bold cursor-pointer shadow-xs"
            :disabled="isArtworkLoading"
            @click="emit('generate', artProvider, artModel)"
          >
            <Icon v-if="isArtworkLoading" name="lucide:loader-circle" class="size-4 animate-spin mr-2" aria-hidden="true" />
            <Icon v-else name="lucide:sparkles" class="size-4 mr-2" aria-hidden="true" />
            <span>Generate Artwork</span>
          </Button>
        </div>

        <!-- Inner state 2: Generating / Refining artwork progress -->
        <div v-else-if="isJobInFlight" class="py-12 text-center space-y-4">
          <Icon name="lucide:loader-circle" class="size-8 animate-spin mx-auto text-primary" aria-hidden="true" />
          <div>
            <h4 class="text-base font-bold text-foreground">
              {{ artworkJobs[0]?.provider === 'gemini' ? 'Refining Artwork Candidate...' : 'Generating Artwork Candidates...' }}
            </h4>
            <p class="text-xs text-muted-foreground mt-1">
              {{ artworkJobs[0]?.provider === 'gemini' ? 'Google Gemini is processing your image-to-image design refinement.' : 'Recraft V4.1 is generating multi-candidate transparent designs.' }}
            </p>
          </div>
        </div>

        <!-- Inner state 3: Artwork Generation Failed -->
        <Card v-else-if="isJobFailed" class="p-8 text-center bg-red-50/60 border-red-200">
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-destructive mb-3">
            <Icon name="lucide:circle-alert" class="size-6" aria-hidden="true" />
          </div>
          <h2 class="text-lg font-bold text-destructive mb-1">Artwork Generation Failed</h2>
          <p class="text-xs text-red-700 max-w-md mx-auto mb-4">
            Reason: {{ latestFailureMessage }}
          </p>
          <div class="flex items-center justify-center gap-3">
            <Button variant="destructive" size="default" class="font-semibold cursor-pointer" @click="emit('regenerate')">
              <Icon name="lucide:rotate-ccw" class="size-4 mr-1.5" aria-hidden="true" />
              <span>Retry Artwork Generation</span>
            </Button>
          </div>
        </Card>

        <!-- Inner state 4: Artwork Generated, Review & Candidates -->
        <div v-else-if="currentAssets.length > 0" class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h4 class="text-sm font-bold text-foreground">
                {{ workflow.state === 'ART_REVIEW' ? 'Review & Select Candidate Design' : 'Artwork Candidates' }}
              </h4>
              <p class="text-xs text-muted-foreground">
                {{ workflow.state === 'ART_REVIEW' ? 'Approve one design to proceed to print production.' : 'Click a candidate to select it and switch the master print design.' }}
              </p>
            </div>
            <Button
              v-if="workflow.state === 'ART_REVIEW'"
              variant="ghost"
              size="sm"
              class="text-xs text-destructive hover:text-red-700 hover:bg-red-50 cursor-pointer"
              @click="emit('rejectAll', artworkJobs[0]?.id, workflow.version)"
            >
              Reject All Options
            </Button>
          </div>

          <Alert v-if="artworkError" variant="destructive">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertDescription>{{ artworkError }}</AlertDescription>
          </Alert>

          <!-- Candidates Grid (Compact 4-Column Responsive Layout) -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
            <Card
              v-for="(asset, idx) in currentAssets"
              :key="asset.id"
              class="overflow-hidden border transition-all cursor-pointer shadow-2xs hover:shadow-xs group/card"
              :class="[
                asset.id === chosenCandidateId
                  ? 'border-emerald-500 ring-2 ring-emerald-500/30 bg-emerald-50/10'
                  : asset.id === selectedCandidateId
                    ? 'border-primary ring-2 ring-primary/30 bg-secondary/30'
                    : 'border-border hover:border-primary/40 bg-card'
              ]"
              @click="selectCandidate(asset.id)"
            >
              <div class="aspect-square bg-[repeating-conic-gradient(#f4f4f5_0%_25%,#ffffff_0%_50%)] bg-[length:12px_12px] relative flex items-center justify-center p-2.5">
                <img
                  v-if="asset.url"
                  :src="asset.url"
                  alt="Candidate Preview"
                  class="object-contain w-full h-full max-h-[150px] transition-transform duration-200 group-hover/card:scale-105"
                  @click.stop="openPreview(asset)"
                >
                <div v-else class="text-muted-foreground text-xs">Preview Loading...</div>

                <Badge
                  v-if="isAssetRefined(asset.id)"
                  variant="outline"
                  class="absolute top-1.5 left-1.5 text-[9px] px-1.5 py-0 bg-purple-50 text-purple-700 border-purple-200 font-semibold gap-1 inline-flex items-center shadow-xs"
                >
                  <Icon name="lucide:sparkles" class="size-2.5 text-purple-600" />
                  <span>Refined</span>
                </Badge>
                <Badge
                  v-else
                  variant="default"
                  class="absolute top-1.5 left-1.5 text-[9px] px-1.5 py-0 font-mono"
                >
                  #{{ idx + 1 }}
                </Badge>

                <Badge
                  v-if="asset.id === chosenCandidateId"
                  variant="success"
                  class="absolute top-1.5 right-1.5 text-[9px] px-1.5 py-0 font-bold shadow-xs gap-0.5 inline-flex items-center"
                >
                  <Icon name="lucide:circle-check" class="size-2.5" aria-hidden="true" />
                  <span>Active Master</span>
                </Badge>
                <Badge
                  v-else-if="asset.id === selectedCandidateId"
                  variant="outline"
                  class="absolute top-1.5 right-1.5 text-[9px] px-1.5 py-0 font-bold bg-primary text-white border-primary shadow-xs"
                >
                  Selected
                </Badge>

                <!-- Zoom Inspect Button Overlay on Hover -->
                <button
                  type="button"
                  title="Inspect design in full resolution"
                  class="absolute bottom-1.5 right-1.5 h-7 w-7 rounded-lg bg-white/95 hover:bg-white text-secondary-foreground hover:text-primary shadow-xs flex items-center justify-center backdrop-blur-xs transition-all cursor-pointer opacity-0 group-hover/card:opacity-100 z-10"
                  @click.stop="openPreview(asset)"
                >
                  <Icon name="lucide:maximize-2" class="size-3.5" aria-hidden="true" />
                </button>
              </div>

              <div class="p-2.5 border-t border-border bg-secondary/30 space-y-2">
                <div class="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span class="font-mono">{{ asset.width }}×{{ asset.height }} · {{ (asset.byte_size / 1024).toFixed(0) }} KB</span>
                  <button
                    type="button"
                    class="text-[10px] font-bold text-primary hover:text-primary-hover flex items-center gap-0.5 cursor-pointer"
                    title="Inspect candidate"
                    @click.stop="openPreview(asset)"
                  >
                    <span>Inspect</span>
                    <Icon name="lucide:zoom-in" class="size-2.5" />
                  </button>
                </div>

                <!-- Gate 2 Review Actions (During ART_REVIEW) -->
                <div v-if="workflow.state === 'ART_REVIEW'" class="grid grid-cols-2 gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    class="text-[11px] h-7 px-1.5 font-medium cursor-pointer"
                    @click.stop="emit('refine', asset.id)"
                  >
                    Refine Option
                  </Button>
                  <Button
                    variant="success"
                    size="sm"
                    class="text-[11px] h-7 px-1.5 font-bold cursor-pointer"
                    @click.stop="emit('approve', asset.id)"
                  >
                    Approve Artwork
                  </Button>
                </div>

                <!-- Approved State: Selection indicator -->
                <div v-else-if="workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'PRODUCTION' || latestProductionJob !== null">
                  <div
                    v-if="asset.id === chosenCandidateId"
                    class="flex items-center justify-center gap-1 py-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 rounded border border-emerald-200"
                  >
                    <Icon name="lucide:circle-check" class="size-3" aria-hidden="true" />
                    <span>Active in Master</span>
                  </div>
                  <Button
                    v-else-if="asset.id === selectedCandidateId"
                    variant="default"
                    size="sm"
                    class="w-full text-[11px] font-bold gap-1 h-7 px-1 cursor-pointer inline-flex items-center shadow-2xs animate-in fade-in"
                    :disabled="isProductionLoading"
                    @click.stop="emit('switchCandidate', asset.id)"
                  >
                    <Icon v-if="isProductionLoading" name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
                    <Icon v-else name="lucide:sparkles" class="size-3" aria-hidden="true" />
                    <span>Switch & Produce</span>
                  </Button>
                  <div
                    v-else
                    class="text-center py-1 text-[10px] text-muted-foreground font-medium"
                  >
                    Click to select
                  </div>
                </div>
              </div>
            </Card>
          </div>

          <!-- Switch & Produce Action Bar (Appears when a different candidate is selected) -->
          <div
            v-if="(workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'PRODUCTION' || latestProductionJob !== null) && selectedCandidateId && selectedCandidateId !== chosenCandidateId"
            class="p-3.5 rounded-xl bg-secondary/50 border border-border flex flex-col sm:flex-row items-center justify-between gap-3 animate-in fade-in slide-in-from-top-1 duration-150"
          >
            <div class="flex items-center gap-3">
              <div
                class="h-10 w-10 rounded-lg overflow-hidden border border-border bg-white shrink-0 p-1 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-primary/40 transition-all"
                title="Inspect in full size"
                @click="getSelectedAsset() && openPreview(getSelectedAsset()!)"
              >
                <img :src="getSelectedAsset()?.url || ''" alt="Candidate" class="w-full h-full object-contain">
              </div>
              <div>
                <h4 class="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <span>Selected Candidate #{{ getSelectedAssetIndex() + 1 }}</span>
                  <Badge variant="outline" class="text-[9px] px-1.5 py-0 bg-blue-50 text-primary border-blue-200 font-semibold">New Choice</Badge>
                </h4>
                <p class="text-[11px] text-secondary-foreground">Switch master print PNG to this artwork and automatically update all your mockups</p>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                class="text-xs h-8 px-3 gap-1 cursor-pointer"
                @click="getSelectedAsset() && openPreview(getSelectedAsset()!)"
              >
                <Icon name="lucide:maximize-2" class="size-3 text-primary" />
                <span>Inspect</span>
              </Button>
              <Button
                variant="default"
                size="sm"
                class="font-bold text-xs h-8 px-4 gap-1.5 shadow-2xs shrink-0 cursor-pointer"
                :disabled="isProductionLoading"
                @click="emit('switchCandidate', selectedCandidateId)"
              >
                <Icon v-if="isProductionLoading" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
                <Icon v-else name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
                <span>{{ isProductionLoading ? 'Producing...' : 'Switch & Produce' }}</span>
              </Button>
            </div>
          </div>

          <!-- Regeneration Option -->
          <div v-if="workflow.state === 'ART_REVIEW'" class="rounded-xl border border-dashed border-border p-4 text-center">
            <p class="text-xs text-muted-foreground mb-2">Not satisfied with any of these candidate options?</p>
            <Button variant="outline" size="sm" class="text-xs gap-1.5 cursor-pointer inline-flex items-center" @click="emit('regenerate')">
              <Icon name="lucide:refresh-cw" class="size-3.5" aria-hidden="true" />
              <span>Regenerate All Options</span>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Candidate Design Full-Size Inspection Modal -->
    <div
      v-if="previewingAsset"
      class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-xs animate-in fade-in duration-150"
      @click.self="previewingAsset = null"
    >
      <div
        class="bg-white rounded-2xl shadow-2xl border border-border max-w-4xl w-full max-h-[94vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150"
        @click.stop
      >
        <!-- Modal Header -->
        <div class="px-5 py-3.5 border-b border-border bg-secondary/30 flex items-center justify-between gap-4">
          <div class="flex items-center gap-2.5 truncate">
            <div class="size-7 rounded-lg bg-blue-50 text-primary border border-blue-200 flex items-center justify-center shrink-0">
              <Icon name="lucide:image" class="size-4" aria-hidden="true" />
            </div>
            <div class="truncate">
              <div class="flex items-center gap-2 flex-wrap">
                <h3 class="text-sm font-bold text-foreground">
                  Candidate Design #{{ getPreviewAssetIndex() + 1 }} of {{ currentAssets.length }}
                </h3>
                <Badge
                  v-if="isAssetRefined(previewingAsset.id)"
                  variant="outline"
                  class="text-[9px] px-1.5 py-0 font-bold bg-purple-50 text-purple-700 border-purple-200 gap-1 inline-flex items-center"
                >
                  <Icon name="lucide:sparkles" class="size-2.5 text-purple-600" />
                  <span>Refined</span>
                </Badge>
                <Badge
                  v-if="previewingAsset.id === chosenCandidateId"
                  variant="success"
                  class="text-[9px] px-1.5 py-0 font-bold gap-0.5 inline-flex items-center"
                >
                  <Icon name="lucide:circle-check" class="size-2.5" />
                  <span>Active Master</span>
                </Badge>
                <Badge
                  v-else-if="previewingAsset.id === selectedCandidateId"
                  variant="outline"
                  class="text-[9px] px-1.5 py-0 font-bold bg-blue-50 text-primary border-blue-200"
                >
                  Selected Option
                </Badge>
              </div>
              <p class="text-[11px] text-muted-foreground font-mono truncate">
                {{ previewingAsset.width || '1024' }}×{{ previewingAsset.height || '1024' }} px · {{ ((previewingAsset.byte_size || 0) / 1024).toFixed(0) }} KB · {{ (previewingAsset.mime_type || 'image/png').toUpperCase() }} · Transparent Alpha
              </p>
            </div>
          </div>

          <!-- Background Surface Switcher Pills -->
          <div class="flex items-center gap-1 bg-secondary/80 p-0.5 rounded-lg border border-border text-[11px] shrink-0">
            <button
              type="button"
              title="Checkerboard Alpha Transparency"
              class="px-2 py-1 rounded-md font-semibold transition-all cursor-pointer inline-flex items-center gap-1"
              :class="previewBg === 'checkerboard' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
              @click="previewBg = 'checkerboard'"
            >
              <Icon name="lucide:grid-2x2" class="size-3 text-primary" />
              <span class="hidden sm:inline">Checkerboard</span>
            </button>
            <button
              type="button"
              title="White Surface"
              class="px-2 py-1 rounded-md font-semibold transition-all cursor-pointer inline-flex items-center gap-1"
              :class="previewBg === 'white' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
              @click="previewBg = 'white'"
            >
              <div class="size-2.5 rounded-full bg-white border border-slate-300 shadow-2xs" />
              <span class="hidden sm:inline">White</span>
            </button>
            <button
              type="button"
              title="Dark Garment Surface"
              class="px-2 py-1 rounded-md font-semibold transition-all cursor-pointer inline-flex items-center gap-1"
              :class="previewBg === 'dark' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
              @click="previewBg = 'dark'"
            >
              <div class="size-2.5 rounded-full bg-slate-900 shadow-2xs" />
              <span class="hidden sm:inline">Dark</span>
            </button>
          </div>

          <button
            type="button"
            class="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center transition-colors cursor-pointer shrink-0"
            @click="previewingAsset = null"
          >
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Modal Viewport Canvas with Left / Right Arrows -->
        <div
          class="relative flex-1 p-4 sm:p-6 flex items-center justify-center min-h-[320px] max-h-[65vh] overflow-hidden select-none transition-colors duration-150"
          :class="{
            'bg-[linear-gradient(45deg,#F1F5F9_25%,transparent_25%),linear-gradient(-45deg,#F1F5F9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#F1F5F9_75%),linear-gradient(-45deg,transparent_75%,#F1F5F9_75%)] bg-[size:16px_16px] bg-[position:0_0,0_8px,8px_-8px,-8px_0px]': previewBg === 'checkerboard',
            'bg-white': previewBg === 'white',
            'bg-slate-950': previewBg === 'dark',
          }"
        >
          <!-- Left Arrow (Previous Candidate) -->
          <button
            v-if="currentAssets.length > 1"
            type="button"
            class="absolute left-3 sm:left-5 top-1/2 -translate-y-1/2 size-9 rounded-full bg-white/90 hover:bg-white text-secondary-foreground hover:text-primary shadow-md flex items-center justify-center backdrop-blur-xs transition-all cursor-pointer z-10 disabled:opacity-30 disabled:pointer-events-none"
            :disabled="getPreviewAssetIndex() <= 0"
            title="Previous Candidate (Left Arrow)"
            @click.stop="navigatePreview(-1)"
          >
            <Icon name="lucide:chevron-left" class="size-5" />
          </button>

          <!-- Candidate Image -->
          <img
            v-if="previewingAsset.url"
            :src="previewingAsset.url"
            :alt="`Candidate ${getPreviewAssetIndex() + 1}`"
            class="max-w-full max-h-[58vh] object-contain rounded-lg shadow-sm transition-all duration-200"
          >

          <!-- Right Arrow (Next Candidate) -->
          <button
            v-if="currentAssets.length > 1"
            type="button"
            class="absolute right-3 sm:right-5 top-1/2 -translate-y-1/2 size-9 rounded-full bg-white/90 hover:bg-white text-secondary-foreground hover:text-primary shadow-md flex items-center justify-center backdrop-blur-xs transition-all cursor-pointer z-10 disabled:opacity-30 disabled:pointer-events-none"
            :disabled="getPreviewAssetIndex() >= currentAssets.length - 1"
            title="Next Candidate (Right Arrow)"
            @click.stop="navigatePreview(1)"
          >
            <Icon name="lucide:chevron-right" class="size-5" />
          </button>
        </div>

        <!-- Modal Footer Controls -->
        <div class="px-5 py-3 border-t border-border bg-secondary/30 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <a
              v-if="previewingAsset.url"
              :href="sanitizeUrl(previewingAsset.url)"
              target="_blank"
              rel="noopener noreferrer"
              :download="`candidate_design_${getPreviewAssetIndex() + 1}.png`"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white border border-border text-secondary-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer shadow-2xs"
            >
              <Icon name="lucide:download" class="size-3.5 text-primary" aria-hidden="true" />
              <span>Download PNG</span>
            </a>
          </div>

          <div class="flex items-center gap-2">
            <!-- Review Stage Actions -->
            <template v-if="workflow.state === 'ART_REVIEW'">
              <Button
                variant="outline"
                size="sm"
                class="text-xs font-medium cursor-pointer"
                @click="emit('refine', previewingAsset.id); previewingAsset = null"
              >
                <Icon name="lucide:sliders" class="size-3.5 mr-1 text-primary" />
                <span>Refine Option</span>
              </Button>
              <Button
                variant="success"
                size="sm"
                class="text-xs font-bold cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
                @click="emit('approve', previewingAsset.id); previewingAsset = null"
              >
                <Icon name="lucide:circle-check" class="size-3.5" />
                <span>Approve This Artwork</span>
              </Button>
            </template>

            <!-- Approved / Production Stage Switch Action -->
            <template v-else-if="workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'PRODUCTION' || latestProductionJob !== null">
              <Button
                v-if="previewingAsset.id !== chosenCandidateId"
                variant="default"
                size="sm"
                class="text-xs font-bold gap-1.5 cursor-pointer shadow-xs"
                :disabled="isProductionLoading"
                @click="emit('switchCandidate', previewingAsset.id); previewingAsset = null"
              >
                <Icon v-if="isProductionLoading" name="lucide:loader-circle" class="size-3.5 animate-spin" />
                <Icon v-else name="lucide:sparkles" class="size-3.5" />
                <span>Switch Master to This Design</span>
              </Button>
              <Badge v-else variant="success" class="text-xs px-3 py-1 font-bold">
                <Icon name="lucide:circle-check" class="size-3.5 mr-1" />
                <span>Active Master Artwork</span>
              </Badge>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
