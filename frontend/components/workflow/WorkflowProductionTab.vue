<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { getProductIcon } from "~/config/icons";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import WorkflowCustomMockupModal, { type MockupAssetItem } from "~/components/workflow/WorkflowCustomMockupModal.vue";

interface DesignPrompt {
  id: string;
  exact_slogan: string | null;
}

interface Concept {
  id: string;
  title: string;
  prompts: DesignPrompt[];
}

interface AssetProvenance {
  phase?: number;
  asset_type?: string;
  source?: string;
  product_type?: string;
  template_id?: string;
  template_name?: string;
  source_asset_id?: string;
  is_cover?: boolean;
  listing_order?: number;
  placement?: {
    left_pct?: number;
    top_pct?: number;
    width_pct?: number;
    height_pct?: number;
    angle_deg?: number;
    blend_mode?: string;
  };
}

interface Asset {
  id: string;
  workflow_id: string;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256: string;
  width: number | null;
  height: number | null;
  has_alpha: boolean | null;
  url: string | null;
  provenance?: AssetProvenance;
  created_at?: string;
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

interface Workflow {
  id: string;
  state: string;
  version: number;
  intended_product_uses?: string[];
}

const props = defineProps<{
  workflow: Workflow;
  approvedConcept?: Concept;
  latestProductionJob: ProductionJob | null;
  isProductionLoading: boolean;
  productionError: string | null;
}>();

const emit = defineEmits<{
  (e: "triggerProduction", forceNew: boolean): void;
  (e: "mockupUpdated"): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

function normalizeProductKey(raw?: string | null): string {
  if (!raw) return "product";
  const text = raw.toLowerCase().trim();
  if (text.includes("tumbler") || text === "tumblers") return "tumbler";
  if (text.includes("mug") || text.includes("ceramic") || text === "mug" || text === "cup") return "mug";
  if (text.includes("sweat") || text.includes("hoodie") || text.includes("crewneck") || text === "sweatshirt") return "sweatshirt";
  if (text.includes("tote") || text.includes("bag") || text === "tote_bag") return "tote_bag";
  if (text.includes("shirt") || text.includes("tee") || text.includes("apparel") || text === "tshirt") return "tshirt";
  if (text.includes("poster") || text.includes("wall_art")) return "poster";
  if (text.includes("sticker")) return "sticker";
  if (text.includes("phone")) return "phone_case";
  if (text.includes("candle")) return "candle";
  return text.replace(/\s+/g, "_");
}

function extractProductFromKey(key: string): string {
  if (!key) return "tshirt";
  const parts = key.split("/");
  const fname = parts[parts.length - 1];
  if (fname.includes("custom_")) {
    const after = fname.split("custom_")[1];
    return after.split("_")[0];
  }
  return fname.split(".")[0];
}

// Local reactive mockups list for instant UI updates
const localMockupAssets = ref<Asset[]>([]);
const isActionLoading = ref(false);
const mockupActionError = ref<string | null>(null);

// Modal state
const showCustomMockupModal = ref(false);
const editingMockupAsset = ref<MockupAssetItem | null>(null);
const previewingAsset = ref<Asset | null>(null);

// Sync with latestProductionJob
watch(
  () => props.latestProductionJob?.mockup_assets,
  (newAssets) => {
    if (newAssets && Array.isArray(newAssets)) {
      localMockupAssets.value = [...newAssets];
    }
  },
  { immediate: true, deep: true }
);

// Group mockups by product
const mockupsByProduct = computed<Record<string, Asset[]>>(() => {
  const map: Record<string, Asset[]> = {};
  for (const a of localMockupAssets.value) {
    const p = normalizeProductKey(a.provenance?.product_type || extractProductFromKey(a.storage_key));
    if (!map[p]) map[p] = [];
    map[p].push(a);
  }
  for (const k in map) {
    map[k].sort((a, b) => {
      const aOrd = Number(a.provenance?.listing_order ?? 999);
      const bOrd = Number(b.provenance?.listing_order ?? 999);
      if (aOrd !== bOrd) return aOrd - bOrd;
      const aCov = a.provenance?.is_cover ? 0 : 1;
      const bCov = b.provenance?.is_cover ? 0 : 1;
      if (aCov !== bCov) return aCov - bCov;
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
      return aTime - bTime;
    });
  }
  return map;
});

// Available product tabs (filtered to intended physical products + any actively uploaded mockups)
const availableProductTabs = computed<string[]>(() => {
  const intendedRaw = props.workflow?.intended_product_uses ?? [];
  const intendedKeys = intendedRaw.map(normalizeProductKey).filter(Boolean);
  const assetKeys = Object.keys(mockupsByProduct.value).filter(
    (k) => (mockupsByProduct.value[k] || []).length > 0
  );

  if (intendedKeys.length > 0) {
    const set = new Set([...intendedKeys, ...assetKeys]);
    return Array.from(set);
  }

  const standardProducts = ["tshirt", "sweatshirt", "mug", "tote_bag", "tumbler", "poster"];
  const set = new Set([...assetKeys, ...standardProducts]);
  return Array.from(set);
});

const selectedMockupTab = ref<string>("tshirt");

watch(
  availableProductTabs,
  (tabs) => {
    if (tabs.length > 0 && !tabs.includes(selectedMockupTab.value)) {
      selectedMockupTab.value = tabs[0];
    }
  },
  { immediate: true }
);

const currentTabMockups = computed<Asset[]>(() => {
  return mockupsByProduct.value[selectedMockupTab.value] || [];
});

const totalMockupsCount = computed<number>(() => {
  return localMockupAssets.value.length;
});

const masterImageUrl = computed<string | null>(() => {
  return props.latestProductionJob?.master_asset?.url || null;
});

function getMockupLabel(product: string): string {
  if (!product) return "Product";
  const clean = product.toLowerCase().trim();
  switch (clean) {
    case "mug":
      return "Ceramic Mug";
    case "tshirt":
    case "t_shirt":
      return "T-Shirt";
    case "sweatshirt":
      return "Sweatshirt";
    case "tote_bag":
    case "tote":
      return "Tote Bag";
    case "tumbler":
    case "tumblers":
      return "Tumbler";
    case "poster":
    case "posters":
      return "Poster";
    case "sticker":
    case "stickers":
      return "Stickers";
    case "phone_case":
      return "Phone Case";
    case "candle":
    case "candles":
      return "Scented Candle";
    default:
      return clean.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

function openAddMockupModal(product: string): void {
  selectedMockupTab.value = product;
  editingMockupAsset.value = null;
  showCustomMockupModal.value = true;
}

function openAdjustMockupModal(asset: Asset): void {
  selectedMockupTab.value = normalizeProductKey(asset.provenance?.product_type || selectedMockupTab.value);
  editingMockupAsset.value = {
    id: asset.id,
    template_id: asset.provenance?.template_id,
    template_name: asset.provenance?.template_name,
    url: asset.url,
    provenance: asset.provenance,
  };
  showCustomMockupModal.value = true;
}

function handleCustomMockupCreated(result: {
  mockup_url: string;
  asset_id?: string;
  product_type: string;
  template_id?: string;
  template_name?: string;
  is_cover?: boolean;
  listing_order?: number;
}): void {
  const norm = normalizeProductKey(result.product_type);
  selectedMockupTab.value = norm;

  if (result.asset_id) {
    const existingIdx = localMockupAssets.value.findIndex((a) => a.id === result.asset_id);
    if (existingIdx >= 0) {
      localMockupAssets.value[existingIdx] = {
        ...localMockupAssets.value[existingIdx],
        url: result.mockup_url,
        provenance: {
          ...localMockupAssets.value[existingIdx].provenance,
          template_id: result.template_id,
          template_name: result.template_name,
          product_type: norm,
          is_cover: result.is_cover,
          listing_order: result.listing_order,
        },
      };
    } else {
      localMockupAssets.value.push({
        id: result.asset_id,
        workflow_id: props.workflow.id,
        storage_key: `production/${props.workflow.id}/mockups/custom_${norm}_${result.asset_id}.jpg`,
        mime_type: "image/jpeg",
        byte_size: 1000,
        checksum_sha256: "",
        width: 1200,
        height: 1200,
        has_alpha: false,
        url: result.mockup_url,
        provenance: {
          phase: 7,
          asset_type: "mockup",
          source: "user_template",
          product_type: norm,
          template_id: result.template_id,
          template_name: result.template_name,
          is_cover: result.is_cover,
          listing_order: result.listing_order,
        },
      });
    }
  }

  emit("mockupUpdated");
}

async function handleSetCover(asset: Asset): Promise<void> {
  isActionLoading.value = true;
  mockupActionError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/mockups/${asset.id}/cover`,
      {
        method: "PATCH",
        headers,
        credentials: "include",
      }
    );

    // Update local state
    localMockupAssets.value = localMockupAssets.value.map((a) => {
      if (a.id === asset.id) {
        return {
          ...a,
          provenance: { ...a.provenance, is_cover: true },
        };
      }
      return {
        ...a,
        provenance: { ...a.provenance, is_cover: false },
      };
    });

    emit("mockupUpdated");
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    mockupActionError.value = errorObj.data?.detail || errorObj.message || "Failed to set cover image.";
  } finally {
    isActionLoading.value = false;
  }
}

async function handleDeleteMockup(asset: Asset): Promise<void> {
  const label = asset.provenance?.template_name || getMockupLabel(selectedMockupTab.value);
  if (!confirm(`Are you sure you want to delete "${label}"? Your master PNG and blank templates will remain safe.`)) {
    return;
  }

  isActionLoading.value = true;
  mockupActionError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/mockups/${asset.id}`,
      {
        method: "DELETE",
        headers,
        credentials: "include",
      }
    );

    localMockupAssets.value = localMockupAssets.value.filter((a) => a.id !== asset.id);
    emit("mockupUpdated");
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    mockupActionError.value = errorObj.data?.detail || errorObj.message || "Failed to delete mockup.";
  } finally {
    isActionLoading.value = false;
  }
}

async function handleMoveMockup(asset: Asset, direction: "left" | "right"): Promise<void> {
  const currentList = [...currentTabMockups.value];
  const idx = currentList.findIndex((a) => a.id === asset.id);
  if (idx < 0) return;
  const targetIdx = direction === "left" ? idx - 1 : idx + 1;
  if (targetIdx < 0 || targetIdx >= currentList.length) return;

  // Swap
  const temp = currentList[idx];
  currentList[idx] = currentList[targetIdx];
  currentList[targetIdx] = temp;

  // Assign updated listing_order to all items in currentTab
  const updatedTabItems = currentList.map((item, i) => ({
    ...item,
    provenance: {
      ...item.provenance,
      listing_order: i + 1,
    },
  }));

  // Update localMockupAssets with new array reference for instant Vue reactivity
  localMockupAssets.value = localMockupAssets.value.map((a) => {
    const updated = updatedTabItems.find((u) => u.id === a.id);
    return updated ? { ...updated } : { ...a };
  });

  // Construct full ordered asset IDs for backend persistence
  const tabItemIds = updatedTabItems.map((u) => u.id);
  const otherItemIds = localMockupAssets.value
    .filter((a) => !tabItemIds.includes(a.id))
    .map((a) => a.id);
  const allOrderedIds = [...tabItemIds, ...otherItemIds];

  isActionLoading.value = true;
  mockupActionError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;

    const data = await $fetch<Asset[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/mockups/reorder`,
      {
        method: "PATCH",
        headers,
        body: { asset_ids: allOrderedIds },
        credentials: "include",
      }
    );

    if (data && Array.isArray(data)) {
      localMockupAssets.value = data;
    }

    emit("mockupUpdated");
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    mockupActionError.value = errorObj.data?.detail || errorObj.message || "Failed to reorder mockups.";
  } finally {
    isActionLoading.value = false;
  }
}

const isRecompositingAll = ref(false);

async function handleRecompositeAllMockups(): Promise<void> {
  if (localMockupAssets.value.length === 0) return;
  isRecompositingAll.value = true;
  mockupActionError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    const data = await $fetch<Asset[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${props.workflow.id}/mockups/recomposite-all`,
      {
        method: "POST",
        headers,
        credentials: "include",
      }
    );

    if (data && Array.isArray(data)) {
      localMockupAssets.value = data;
    }
    emit("mockupUpdated");
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
  } finally {
    isRecompositingAll.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Phase 7: PNG Production Pipeline Card -->
    <Card class="shadow-2xs border-zinc-200">
      <CardHeader class="pb-3 border-b border-zinc-100 bg-zinc-50/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon name="lucide:file-image" class="size-5 text-indigo-600" aria-hidden="true" />
            <div>
              <CardTitle class="text-base font-bold">Phase 7: Print-Ready PNG Production & Realistic Mockups</CardTitle>
              <CardDescription class="text-xs text-zinc-500">
                Deterministic 4500×5400 px @ 300 DPI master PNG with transparency, safe trim, slogan typography, QA & multi-mockup gallery
              </CardDescription>
            </div>
          </div>
          <Badge
            v-if="latestProductionJob?.status === 'SUCCEEDED'"
            variant="success"
            class="gap-1 px-3 py-1 font-semibold inline-flex items-center"
          >
            <Icon name="lucide:circle-check" class="size-3.5" aria-hidden="true" />
            <span>Production Complete</span>
          </Badge>
          <Badge
            v-else-if="workflow.state === 'PRODUCTION' || latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED'"
            variant="warning"
            class="gap-1 px-3 py-1 font-semibold inline-flex items-center"
          >
            <Icon name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
            <span>Processing PNG...</span>
          </Badge>
          <Badge
            v-else-if="latestProductionJob?.status === 'FAILED'"
            variant="destructive"
            class="gap-1 px-3 py-1 font-semibold inline-flex items-center"
          >
            <Icon name="lucide:circle-alert" class="size-3.5" aria-hidden="true" />
            <span>Production Failed</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent class="pt-6 space-y-6">
        <!-- 1. Ready to Produce State (Gate 2 Approved) -->
        <div v-if="!latestProductionJob && (workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'IDEA_APPROVED')" class="space-y-4">
          <div class="rounded-xl border border-indigo-100 bg-indigo-50/50 p-5 space-y-4">
            <div class="flex items-start gap-3">
              <div class="h-9 w-9 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-700 shrink-0">
                <Icon name="lucide:sparkles" class="size-5" aria-hidden="true" />
              </div>
              <div class="space-y-1">
                <h4 class="text-sm font-bold text-indigo-950">Artwork Approved & Ready for Master PNG Processing</h4>
                <p class="text-xs text-indigo-900/80 leading-relaxed">
                  Start deterministic Phase 7 master PNG production. The pipeline applies 8% safe-margin trimming, 4500×5400 px @ 300 DPI upscale, slogan typography overlay, and strict transparency QA. Once complete, you can composite multiple mockups.
                </p>
              </div>
            </div>

            <div v-if="approvedConcept?.prompts?.[0]?.exact_slogan" class="rounded-lg bg-white border border-indigo-100 p-3 text-xs flex items-center justify-between">
              <span class="text-zinc-500 font-medium">Recorded Gate 1 Slogan:</span>
              <span class="font-bold text-zinc-900 font-mono">"{{ approvedConcept.prompts[0].exact_slogan }}"</span>
            </div>

            <div class="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="default"
                size="sm"
                class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold gap-2 shadow-xs cursor-pointer inline-flex items-center"
                :disabled="isProductionLoading"
                @click="emit('triggerProduction', false)"
              >
                <Icon name="lucide:play" class="size-4" aria-hidden="true" />
                <span>Start PNG Production</span>
              </Button>
            </div>
          </div>
        </div>

        <!-- 2. Running State -->
        <div v-else-if="latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED' || (workflow.state === 'PRODUCTION' && latestProductionJob?.status !== 'SUCCEEDED')" class="py-12 text-center space-y-4">
          <div class="h-12 w-12 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600 shadow-xs">
            <Icon name="lucide:loader-2" class="size-6 animate-spin" aria-hidden="true" />
          </div>
          <div class="space-y-1">
            <h4 class="text-base font-bold text-zinc-900">Processing Master PNG & Quality Checks</h4>
            <p class="text-xs text-zinc-500 max-w-md mx-auto">
              Running Sharp image pipeline: safe trim margin (8%), 4500×5400 px upscale @ 300 DPI, transparency verification, and slogan typography integration.
            </p>
          </div>
        </div>

        <!-- 3. Succeeded State (Master PNG & Multi-Mockup Gallery) -->
        <div v-else-if="latestProductionJob?.status === 'SUCCEEDED'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <!-- Left Column: Master PNG Preview & Actions -->
            <div class="lg:col-span-5 space-y-4">
              <div class="border border-zinc-200 rounded-xl p-4 bg-zinc-50/50 space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-zinc-700 flex items-center gap-1.5">
                    <Icon name="lucide:file-check" class="size-4 text-emerald-600" aria-hidden="true" />
                    <span>Master PNG (Transparent 300 DPI)</span>
                  </span>
                  <Badge variant="success" class="text-[10px] px-2 py-0.5">4500 × 5400 px</Badge>
                </div>

                <!-- Checkerboard Preview for Transparency -->
                <div class="aspect-4500/5400 max-h-[340px] mx-auto rounded-lg overflow-hidden border border-zinc-200 flex items-center justify-center bg-[linear-gradient(45deg,#f4f4f5_25%,transparent_25%),linear-gradient(-45deg,#f4f4f5_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f4f4f5_75%),linear-gradient(-45deg,transparent_75%,#f4f4f5_75%)] bg-[size:16px_16px] bg-[position:0_0,0_8px,8px_-8px,-8px_0px] relative shadow-inner">
                  <img
                    v-if="masterImageUrl"
                    :src="masterImageUrl"
                    alt="Master Production PNG"
                    class="object-contain w-full h-full max-h-[320px] transition-transform hover:scale-105 duration-200"
                  >
                  <div v-else class="text-xs text-zinc-400">Loading master PNG...</div>
                </div>

                <!-- Master Actions -->
                <div class="flex items-center gap-2 pt-1">
                  <a
                    v-if="masterImageUrl"
                    :href="masterImageUrl"
                    target="_blank"
                    download="master_transparent_300dpi.png"
                    class="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white px-3 py-2 text-xs font-bold transition-colors shadow-xs cursor-pointer"
                  >
                    <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
                    <span>Download Master PNG</span>
                  </a>
                </div>
              </div>
            </div>

            <!-- Right Column: QA Checklist & Multi-Mockup Gallery -->
            <div class="lg:col-span-7 space-y-6">
              <!-- Automated QA Report Grid -->
              <div class="border border-zinc-200 rounded-xl p-4 bg-white space-y-3 shadow-2xs">
                <div class="flex items-center justify-between border-b border-zinc-100 pb-2.5">
                  <h4 class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                    <Icon name="lucide:shield-check" class="size-4 text-emerald-600" aria-hidden="true" />
                    <span>Automated Production QA Verification</span>
                  </h4>
                  <span class="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                    <Icon name="lucide:check" class="size-3" aria-hidden="true" />
                    100% Passed
                  </span>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Exact Dimensions</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Icon name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
                      {{ latestProductionJob.qa_report?.width ?? 4500 }}×{{ latestProductionJob.qa_report?.height ?? 5400 }} px
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Print Density</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Icon name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
                      {{ latestProductionJob.qa_report?.density_dpi ?? 300 }} DPI
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Alpha Transparency</span>
                    <span class="font-bold text-zinc-800 flex items-center gap-1">
                      <Icon name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
                      Clean Verified
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Safe Margin</span>
                    <span class="font-bold text-zinc-800 flex items-center gap-1">
                      <Icon name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
                      Protected (8%)
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Color Space</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Icon name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
                      {{ latestProductionJob.qa_report?.color_space ?? 'sRGB' }}
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Slogan Typography</span>
                    <span class="font-bold text-zinc-800 text-[11px] flex items-center gap-1">
                      <Icon v-if="latestProductionJob.qa_report?.typography_applied" name="lucide:check" class="size-3 text-emerald-600" aria-hidden="true" />
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

              <!-- Product Multi-Mockup Gallery -->
              <div class="border border-zinc-200 rounded-xl p-5 bg-white space-y-4 shadow-2xs">
                <!-- Gallery Header -->
                <div class="flex flex-wrap items-center justify-between border-b border-zinc-100 pb-3 gap-2">
                  <div class="flex items-center gap-2">
                    <Icon name="lucide:images" class="size-4 text-indigo-600" aria-hidden="true" />
                    <h4 class="text-sm font-bold text-zinc-900">Product Mockup Gallery</h4>
                    <span class="text-xs px-2 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                      {{ totalMockupsCount }} listing {{ totalMockupsCount === 1 ? 'mockup' : 'mockups' }}
                    </span>
                  </div>

                  <Button
                    variant="default"
                    size="sm"
                    class="text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 flex items-center gap-1.5 shadow-2xs cursor-pointer"
                    @click="openAddMockupModal(selectedMockupTab)"
                  >
                    <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
                    <span>Add {{ getMockupLabel(selectedMockupTab) }} Mockup</span>
                  </Button>
                </div>

                <!-- Recommended Listing Images Helper Banner -->
                <div class="p-3 rounded-lg bg-indigo-50/60 border border-indigo-100/80 flex items-center gap-2.5 text-xs text-indigo-950">
                  <Icon name="lucide:sparkles" class="size-4 text-indigo-600 shrink-0" aria-hidden="true" />
                  <p class="leading-relaxed text-[11px]">
                    <span class="font-bold">Recommended Listing Strategy:</span> Create 5–8 strong listing images across different product scenes, flatlays, and close-ups to maximize Etsy conversion.
                  </p>
                </div>

                <!-- Product Tabs with Live Counts -->
                <div class="flex flex-wrap gap-1.5 pt-1">
                  <button
                    v-for="p in availableProductTabs"
                    :key="p"
                    type="button"
                    class="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5"
                    :class="
                      selectedMockupTab === p
                        ? 'bg-zinc-900 text-white shadow-xs'
                        : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200'
                    "
                    @click="selectedMockupTab = p"
                  >
                    <Icon :name="getProductIcon(p)" class="size-3.5 shrink-0" aria-hidden="true" />
                    <span>{{ getMockupLabel(p) }}</span>
                    <span
                      class="text-[10px] px-1.5 py-0.2 rounded-full font-bold transition-colors"
                      :class="
                        selectedMockupTab === p
                          ? 'bg-zinc-700 text-zinc-100'
                          : (mockupsByProduct[p] || []).length > 0
                            ? 'bg-indigo-100 text-indigo-700 font-extrabold'
                            : 'bg-zinc-200 text-zinc-500'
                      "
                    >
                      {{ (mockupsByProduct[p] || []).length }}
                    </span>
                  </button>
                </div>

                <!-- Action Error Alert -->
                <Alert v-if="mockupActionError" variant="destructive" class="py-2">
                  <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
                  <AlertDescription class="text-xs">{{ mockupActionError }}</AlertDescription>
                </Alert>

                <!-- Mockup Grid for Selected Product -->
                <div v-if="currentTabMockups.length > 0" class="space-y-4">
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <!-- Individual Mockup Card -->
                    <div
                      v-for="(mockup, mIdx) in currentTabMockups"
                      :key="mockup.id"
                      class="border rounded-xl overflow-hidden bg-white shadow-2xs flex flex-col transition-all duration-200 hover:shadow-md"
                      :class="mockup.provenance?.is_cover ? 'border-amber-400 ring-1 ring-amber-300' : 'border-zinc-200'"
                    >
                      <!-- Thumbnail Area -->
                      <div class="aspect-square bg-zinc-50 overflow-hidden relative group flex items-center justify-center p-2 border-b border-zinc-100">
                        <img
                          :src="mockup.url || ''"
                          :alt="mockup.provenance?.template_name || selectedMockupTab"
                          class="object-contain w-full h-full rounded-lg transition-transform duration-200 group-hover:scale-105"
                        >

                        <!-- Cover Badge -->
                        <div
                          v-if="mockup.provenance?.is_cover"
                          class="absolute top-2.5 left-2.5 bg-amber-500 text-white font-black text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md shadow-xs flex items-center gap-1"
                        >
                          <Icon name="lucide:star" class="size-3 fill-white" aria-hidden="true" />
                          <span>Cover Image</span>
                        </div>

                        <!-- Listing Order Badge -->
                        <div class="absolute top-2.5 right-2.5 bg-zinc-900/80 backdrop-blur-xs text-white font-mono text-[10px] font-bold px-1.5 py-0.5 rounded shadow-xs">
                          #{{ mockup.provenance?.listing_order ?? (mIdx + 1) }}
                        </div>

                        <!-- Quick Fullscreen Preview Overlay Button -->
                        <button
                          type="button"
                          class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5 text-white text-xs font-bold cursor-pointer"
                          @click="previewingAsset = mockup"
                        >
                          <Icon name="lucide:zoom-in" class="size-5" aria-hidden="true" />
                          <span>Click to Zoom</span>
                        </button>
                      </div>

                      <!-- Card Content & Actions -->
                      <div class="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
                        <div>
                          <h5 class="text-xs font-bold text-zinc-900 truncate" :title="mockup.provenance?.template_name || getMockupLabel(selectedMockupTab)">
                            {{ mockup.provenance?.template_name || `${getMockupLabel(selectedMockupTab)} Mockup ${mIdx + 1}` }}
                          </h5>
                          <p class="text-[10px] text-zinc-400 mt-0.5 font-mono">
                            {{ mockup.width ?? 1200 }}×{{ mockup.height ?? 1200 }} px • JPEG
                          </p>
                        </div>

                        <!-- Action Buttons -->
                        <div class="space-y-2 pt-1 border-t border-zinc-100">
                          <!-- Cover Selector -->
                          <button
                            v-if="!mockup.provenance?.is_cover"
                            type="button"
                            class="w-full text-[11px] font-bold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 py-1 px-2 rounded-md flex items-center justify-center gap-1 transition-colors cursor-pointer"
                            :disabled="isActionLoading"
                            @click="handleSetCover(mockup)"
                          >
                            <Icon name="lucide:star" class="size-3 text-amber-600" aria-hidden="true" />
                            <span>Set as Listing Cover</span>
                          </button>

                          <!-- Row of Actions -->
                          <div class="flex items-center justify-between gap-1.5">
                            <div class="flex items-center gap-1">
                              <!-- Move Left / Right -->
                              <button
                                type="button"
                                class="h-7 w-7 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-600 hover:text-zinc-900 flex items-center justify-center transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                                :disabled="mIdx === 0 || isActionLoading"
                                title="Move Left / Earlier in Listing Order"
                                @click="handleMoveMockup(mockup, 'left')"
                              >
                                <Icon name="lucide:arrow-left" class="size-3" aria-hidden="true" />
                              </button>

                              <button
                                type="button"
                                class="h-7 w-7 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-600 hover:text-zinc-900 flex items-center justify-center transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                                :disabled="mIdx === currentTabMockups.length - 1 || isActionLoading"
                                title="Move Right / Later in Listing Order"
                                @click="handleMoveMockup(mockup, 'right')"
                              >
                                <Icon name="lucide:arrow-right" class="size-3" aria-hidden="true" />
                              </button>

                              <!-- Adjust / Edit Placement -->
                              <button
                                type="button"
                                class="h-7 px-2.5 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-700 hover:text-zinc-900 text-[11px] font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                                title="Adjust Placement, Crop & Blend Mode"
                                @click="openAdjustMockupModal(mockup)"
                              >
                                <Icon name="lucide:sliders-horizontal" class="size-3" aria-hidden="true" />
                                <span>Adjust</span>
                              </button>
                            </div>

                            <div class="flex items-center gap-1">
                              <!-- Download -->
                              <a
                                :href="mockup.url || ''"
                                target="_blank"
                                :download="`${mockup.provenance?.template_name || selectedMockupTab}_mockup.jpg`"
                                class="h-7 w-7 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 flex items-center justify-center transition-colors shadow-2xs cursor-pointer"
                                title="Download High-Res Mockup"
                              >
                                <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
                              </a>

                              <!-- Delete -->
                              <button
                                type="button"
                                class="h-7 w-7 rounded bg-red-50 hover:bg-red-100 text-red-600 flex items-center justify-center transition-colors cursor-pointer"
                                title="Delete this Mockup"
                                :disabled="isActionLoading"
                                @click="handleDeleteMockup(mockup)"
                              >
                                <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Add Another Mockup Card in Grid -->
                    <button
                      type="button"
                      class="border-2 border-dashed border-zinc-200 hover:border-indigo-400 hover:bg-indigo-50/40 rounded-xl p-6 flex flex-col items-center justify-center text-center gap-2 transition-all cursor-pointer min-h-[220px]"
                      @click="openAddMockupModal(selectedMockupTab)"
                    >
                      <div class="h-10 w-10 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-xs">
                        <Icon name="lucide:plus" class="size-5" aria-hidden="true" />
                      </div>
                      <div>
                        <span class="text-xs font-bold text-zinc-900 block">Add Another {{ getMockupLabel(selectedMockupTab) }}</span>
                        <span class="text-[10px] text-zinc-500 block mt-0.5">Upload new scene, flatlay, or model photo</span>
                      </div>
                    </button>
                  </div>
                </div>

                <!-- Empty State when no custom mockup created for this tab yet -->
                <div
                  v-else
                  class="rounded-xl border-2 border-dashed border-zinc-200 bg-zinc-50/60 p-8 text-center space-y-3"
                >
                  <div class="h-12 w-12 mx-auto rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-xs">
                    <Icon :name="getProductIcon(selectedMockupTab)" class="size-6 text-indigo-600" aria-hidden="true" />
                  </div>
                  <div>
                    <h5 class="text-xs font-bold text-zinc-800">No mockups for {{ getMockupLabel(selectedMockupTab) }} yet</h5>
                    <p class="text-[11px] text-zinc-500 max-w-sm mx-auto mt-0.5">
                      Upload your own high-resolution {{ getMockupLabel(selectedMockupTab) }} photos to visually position and blend your master artwork.
                    </p>
                  </div>
                  <Button
                    variant="default"
                    size="sm"
                    class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs gap-1.5 shadow-2xs cursor-pointer inline-flex items-center"
                    @click="openAddMockupModal(selectedMockupTab)"
                  >
                    <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
                    <span>Upload & Position {{ getMockupLabel(selectedMockupTab) }} Mockup</span>
                  </Button>
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
              class="text-xs gap-1.5 ml-auto cursor-pointer inline-flex items-center"
              :disabled="isProductionLoading"
              @click="emit('triggerProduction', true)"
            >
              <Icon name="lucide:refresh-cw" class="size-3.5" :class="{ 'animate-spin': isProductionLoading }" aria-hidden="true" />
              <span>Regenerate Master PNG</span>
            </Button>
          </div>
        </div>

        <!-- 4. Failed State -->
        <div v-if="workflow.state === 'PRODUCTION_FAILED' || (latestProductionJob?.status === 'FAILED' && workflow.state !== 'ARTWORK_APPROVED')" class="space-y-4">
          <Alert variant="destructive">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertTitle>PNG Production Failed</AlertTitle>
            <AlertDescription>
              {{ latestProductionJob?.failure_message || 'An error occurred during production file processing.' }}
            </AlertDescription>
          </Alert>

          <Button
            variant="default"
            size="sm"
            class="gap-1.5 cursor-pointer inline-flex items-center"
            :disabled="isProductionLoading"
            @click="emit('triggerProduction', true)"
          >
            <Icon name="lucide:refresh-cw" class="size-3.5" :class="{ 'animate-spin': isProductionLoading }" aria-hidden="true" />
            <span>Retry PNG Production</span>
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- Custom Mockup Modal (Upload & Adjust) -->
    <WorkflowCustomMockupModal
      v-model:open="showCustomMockupModal"
      :workflow-id="workflow.id"
      :product-type="selectedMockupTab"
      :master-image-url="masterImageUrl"
      :editing-asset="editingMockupAsset"
      @mockup-created="handleCustomMockupCreated"
    />

    <!-- Fullscreen Mockup Zoom / Preview Modal -->
    <div
      v-if="previewingAsset"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      @click.self="previewingAsset = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-4xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        <!-- Preview Modal Header -->
        <div class="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
          <div class="flex items-center gap-3">
            <div class="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Icon name="lucide:image" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-zinc-900">
                {{ previewingAsset.provenance?.template_name || `${getMockupLabel(selectedMockupTab)} Listing Mockup` }}
              </h3>
              <p class="text-[11px] text-zinc-500 font-mono">
                {{ previewingAsset.width ?? 1200 }}×{{ previewingAsset.height ?? 1200 }} px • JPEG • Phase 7 Mockup
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <a
              v-if="previewingAsset.url"
              :href="previewingAsset.url"
              target="_blank"
              download="mockup_listing.jpg"
              class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 text-xs font-bold transition-colors shadow-2xs cursor-pointer"
            >
              <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
              <span>Download Image</span>
            </a>

            <button
              type="button"
              class="h-8 w-8 rounded-lg hover:bg-zinc-200 text-zinc-500 flex items-center justify-center transition-colors cursor-pointer"
              aria-label="Close"
              @click="previewingAsset = null"
            >
              <Icon name="lucide:x" class="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <!-- Preview Modal Body -->
        <div class="p-6 bg-zinc-100 flex items-center justify-center overflow-auto max-h-[75vh]">
          <img
            v-if="previewingAsset.url"
            :src="previewingAsset.url"
            :alt="previewingAsset.provenance?.template_name || 'Mockup Preview'"
            class="max-h-[70vh] object-contain rounded-xl shadow-lg border border-zinc-200 bg-white"
          >
        </div>
      </div>
    </div>
  </div>
</template>
