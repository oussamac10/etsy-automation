<script setup lang="ts">
import { ref, watch } from "vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Label from "~/components/ui/Label.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

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

interface ProductionJob {
  id: string;
  status: string;
  source_asset_id: string | null;
}

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
  return props.artworkJobs[0]?.assets?.find((a) => a.id === selectedCandidateId.value);
}

function getSelectedAssetIndex(): number {
  const assets = props.artworkJobs[0]?.assets || [];
  return assets.findIndex((a) => a.id === selectedCandidateId.value);
}
</script>

<template>
  <div class="space-y-6">
    <!-- Phase 6 Card -->
    <Card class="shadow-2xs">
      <CardHeader class="pb-4 border-b border-zinc-100 bg-zinc-50/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon name="lucide:image" class="size-5 text-indigo-600" aria-hidden="true" />
            <div>
              <CardTitle class="text-lg font-bold">Phase 6: Artwork Generation & Approval (Gate 2)</CardTitle>
              <CardDescription class="text-xs text-zinc-500">
                Select provider/model and approve the generated candidate design before producing print files.
              </CardDescription>
            </div>
          </div>
          <Badge v-if="workflow.state === 'ARTWORK_APPROVED' || latestProductionJob !== null" variant="success" class="gap-1 px-3 py-1 font-semibold inline-flex items-center">
            <Icon name="lucide:check" class="size-3" aria-hidden="true" />
            <span>Artwork Approved</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent class="space-y-6 p-6">
        <!-- Selected Concept Info -->
        <div v-if="approvedConcept" class="rounded-xl border border-zinc-200/80 bg-zinc-50/60 p-4 text-sm space-y-3">
          <div>
            <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-700">Locked Concept</span>
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
                class="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-500"
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
                class="flex h-9 w-full rounded-md border border-zinc-200 bg-zinc-100 px-3 py-1 text-sm text-zinc-500 shadow-2xs"
              >
            </div>
          </div>

          <Button
            variant="default"
            size="lg"
            class="w-full text-base font-bold bg-indigo-600 hover:bg-indigo-700 cursor-pointer shadow-xs"
            :disabled="isArtworkLoading"
            @click="emit('generate', artProvider, artModel)"
          >
            <Icon v-if="isArtworkLoading" name="lucide:loader-circle" class="size-4 animate-spin mr-2" aria-hidden="true" />
            <Icon v-else name="lucide:sparkles" class="size-4 mr-2" aria-hidden="true" />
            <span>Generate Artwork</span>
          </Button>
        </div>

        <!-- Inner state 2: Generating artwork progress -->
        <div v-else-if="isArtworkLoading || (artworkJobs.length > 0 && artworkJobs[0]?.status === 'processing')" class="py-12 text-center space-y-4">
          <Icon name="lucide:loader-circle" class="size-8 animate-spin mx-auto text-indigo-600" aria-hidden="true" />
          <div>
            <h4 class="text-base font-bold text-zinc-900">Generating Artwork Candidates...</h4>
            <p class="text-xs text-zinc-500 mt-1">Recraft V4.1 is generating multi-candidate transparent designs.</p>
          </div>
        </div>

        <!-- Inner state 3: Artwork Generated, Review & Candidates -->
        <div v-else-if="artworkJobs.length > 0 && artworkJobs[0]?.assets && artworkJobs[0].assets.length > 0" class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h4 class="text-sm font-bold text-zinc-900">
                {{ workflow.state === 'ART_REVIEW' ? 'Review & Select Candidate Design' : 'Artwork Candidates' }}
              </h4>
              <p class="text-xs text-zinc-500">
                {{ workflow.state === 'ART_REVIEW' ? 'Approve one design to proceed to print production.' : 'Click a candidate to select it and switch the master print design.' }}
              </p>
            </div>
            <Button
              v-if="workflow.state === 'ART_REVIEW'"
              variant="ghost"
              size="sm"
              class="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 cursor-pointer"
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
              v-for="(asset, idx) in artworkJobs[0]?.assets"
              :key="asset.id"
              class="overflow-hidden border transition-all cursor-pointer shadow-2xs hover:shadow-xs"
              :class="[
                asset.id === chosenCandidateId
                  ? 'border-emerald-500 ring-2 ring-emerald-500/30 bg-emerald-50/10'
                  : asset.id === selectedCandidateId
                    ? 'border-indigo-600 ring-2 ring-indigo-500/30 bg-indigo-50/20'
                    : 'border-zinc-200 hover:border-zinc-300 bg-white'
              ]"
              @click="selectCandidate(asset.id)"
            >
              <div class="aspect-square bg-[repeating-conic-gradient(#f4f4f5_0%_25%,#ffffff_0%_50%)] bg-[length:12px_12px] relative flex items-center justify-center p-2.5">
                <img
                  v-if="asset.url"
                  :src="asset.url"
                  alt="Candidate Preview"
                  class="object-contain w-full h-full max-h-[150px] transition-transform hover:scale-105"
                >
                <div v-else class="text-zinc-400 text-xs">Preview Loading...</div>
                <Badge variant="default" class="absolute top-1.5 left-1.5 text-[9px] px-1.5 py-0 font-mono">
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
                  class="absolute top-1.5 right-1.5 text-[9px] px-1.5 py-0 font-bold bg-indigo-600 text-white border-indigo-600 shadow-xs"
                >
                  Selected
                </Badge>
              </div>

              <div class="p-2.5 border-t border-zinc-100 bg-zinc-50/50 space-y-2">
                <div class="flex items-center justify-between text-[10px] text-zinc-500">
                  <span class="font-mono">{{ asset.width }}×{{ asset.height }} · {{ (asset.byte_size / 1024).toFixed(0) }} KB</span>
                  <span class="uppercase text-[9px] font-bold text-zinc-600">{{ asset.mime_type.split('/')[1] }}</span>
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
                    class="flex items-center justify-center gap-1 py-1 text-[11px] font-bold text-emerald-700 bg-emerald-100/60 rounded border border-emerald-200"
                  >
                    <Icon name="lucide:circle-check" class="size-3" aria-hidden="true" />
                    <span>Active in Master</span>
                  </div>
                  <div
                    v-else-if="asset.id === selectedCandidateId"
                    class="flex items-center justify-center gap-1 py-1 text-[11px] font-bold text-indigo-700 bg-indigo-100/60 rounded border border-indigo-200"
                  >
                    <Icon name="lucide:check" class="size-3" aria-hidden="true" />
                    <span>Ready to Switch</span>
                  </div>
                  <div
                    v-else
                    class="text-center py-1 text-[10px] text-zinc-400 font-medium"
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
            class="p-3.5 rounded-xl bg-indigo-50/80 border border-indigo-200 flex flex-col sm:flex-row items-center justify-between gap-3 animate-in fade-in slide-in-from-top-1 duration-150"
          >
            <div class="flex items-center gap-3">
              <div class="h-10 w-10 rounded-lg overflow-hidden border border-indigo-200 bg-white shrink-0 p-1 flex items-center justify-center">
                <img :src="getSelectedAsset()?.url || ''" alt="Candidate" class="w-full h-full object-contain" />
              </div>
              <div>
                <h4 class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                  <span>Selected Candidate #{{ getSelectedAssetIndex() + 1 }}</span>
                  <Badge variant="outline" class="text-[9px] px-1.5 py-0 bg-indigo-100 text-indigo-800 border-indigo-200 font-semibold">New Choice</Badge>
                </h4>
                <p class="text-[11px] text-zinc-600">Switch master print PNG to this artwork and automatically update all your mockups</p>
              </div>
            </div>

            <Button
              variant="default"
              size="sm"
              class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs h-8 px-4 gap-1.5 shadow-2xs shrink-0 cursor-pointer"
              :disabled="isProductionLoading"
              @click="emit('switchCandidate', selectedCandidateId)"
            >
              <Icon v-if="isProductionLoading" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
              <Icon v-else name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
              <span>{{ isProductionLoading ? 'Producing...' : 'Switch & Produce' }}</span>
            </Button>
          </div>

          <!-- Regeneration Option -->
          <div v-if="workflow.state === 'ART_REVIEW'" class="rounded-xl border border-dashed border-zinc-200 p-4 text-center">
            <p class="text-xs text-zinc-500 mb-2">Not satisfied with any of these candidate options?</p>
            <Button variant="outline" size="sm" class="text-xs gap-1.5 cursor-pointer inline-flex items-center" @click="emit('regenerate')">
              <Icon name="lucide:refresh-cw" class="size-3.5" aria-hidden="true" />
              <span>Regenerate All Options</span>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
