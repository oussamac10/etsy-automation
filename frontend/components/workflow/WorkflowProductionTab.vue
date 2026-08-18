<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type { ProductionJob } from "~/types/production";
import type { MockupAsset } from "~/types/mockup";
import { useMockups } from "~/composables/useMockups";
import { getApiErrorMessage } from "~/utils/api";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import ProductionStatusCard from "~/components/workflow/production/ProductionStatusCard.vue";
import MasterPngCard from "~/components/workflow/production/MasterPngCard.vue";
import ProductionQaCard from "~/components/workflow/production/ProductionQaCard.vue";
import MockupGallery from "~/components/workflow/production/MockupGallery.vue";
import WorkflowCustomMockupModal, { type MockupAssetItem } from "~/components/workflow/WorkflowCustomMockupModal.vue";
import DeleteConfirmModal from "~/components/ui/DeleteConfirmModal.vue";
import { getProductLabel, normalizeProductKey } from "~/utils/mockupProducts";

interface DesignPrompt {
  id: string;
  exact_slogan: string | null;
  intended_product_uses?: string[];
}

interface Concept {
  id: string;
  title: string;
  intended_product_uses?: string[];
  prompts: DesignPrompt[];
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
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

const activeMasterAssetId = computed(
  () => props.latestProductionJob?.output_asset_id || props.latestProductionJob?.master_asset?.id || null
);

const {
  localMockupAssets,
  selectedMockupTab,
  mockupsByProduct,
  availableProductTabs,
  currentTabMockups,
  syncMockupAssets,
  deleteMockup,
} = useMockups(
  () => activeMasterAssetId.value,
  () => props.workflow?.intended_product_uses,
);

const renderNonce = ref<number>(Date.now());
const isActionLoading = ref(false);
const mockupActionError = ref<string | null>(null);

// Modal state
const showCustomMockupModal = ref(false);
const editingMockupAsset = ref<MockupAssetItem | null>(null);

// Sync with latestProductionJob
watch(
  () => props.latestProductionJob,
  (newJob) => {
    if (newJob?.mockup_assets && Array.isArray(newJob.mockup_assets)) {
      syncMockupAssets(newJob.mockup_assets);
    }
    renderNonce.value = Date.now();
  },
  { immediate: true, deep: true }
);

const totalMockupsCount = computed<number>(() => {
  return Object.values(mockupsByProduct.value).reduce((sum, list) => sum + list.length, 0);
});

const masterImageUrl = computed<string | null>(() => {
  return props.latestProductionJob?.master_asset?.url || null;
});

function openAddMockupModal(product: string): void {
  selectedMockupTab.value = product;
  editingMockupAsset.value = null;
  showCustomMockupModal.value = true;
}

function openAdjustMockupModal(asset: MockupAsset): void {
  selectedMockupTab.value = asset.provenance?.product_type || selectedMockupTab.value;
  editingMockupAsset.value = {
    id: asset.id,
    template_id: asset.provenance?.template_id || undefined,
    template_name: asset.provenance?.template_name || undefined,
    url: asset.url || undefined,
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
  selectedMockupTab.value = result.product_type;

  if (result.asset_id) {
    const existingIdx = localMockupAssets.value.findIndex((a) => a.id === result.asset_id);
    if (existingIdx >= 0) {
      const updated = [...localMockupAssets.value];
      updated[existingIdx] = {
        ...updated[existingIdx],
        url: result.mockup_url,
        provenance: {
          ...updated[existingIdx].provenance,
          template_id: result.template_id,
          template_name: result.template_name,
          product_type: result.product_type,
          is_cover: result.is_cover,
          listing_order: result.listing_order,
        },
      };
      localMockupAssets.value = updated;
    } else {
      localMockupAssets.value = [
        ...localMockupAssets.value,
        {
          id: result.asset_id,
          workflow_id: props.workflow.id,
          derived_from_id: activeMasterAssetId.value,
          storage_key: `production/${props.workflow.id}/mockups/custom_${result.product_type}_${result.asset_id}.jpg`,
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
            product_type: result.product_type,
            source_asset_id: activeMasterAssetId.value || undefined,
            template_id: result.template_id,
            template_name: result.template_name,
            is_cover: result.is_cover,
            listing_order: result.listing_order,
          },
        },
      ];
    }
  }

  renderNonce.value = Date.now();
  emit("mockupUpdated");
}

async function handleSetCover(asset: MockupAsset): Promise<void> {
  isActionLoading.value = true;
  mockupActionError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    await $fetch(`${apiBase}/api/v1/workflows/${props.workflow.id}/mockups/${asset.id}/cover`, {
      method: "PATCH",
      headers,
      credentials: "include",
    });

    localMockupAssets.value = localMockupAssets.value.map((a) => ({
      ...a,
      provenance: { ...a.provenance, is_cover: a.id === asset.id },
    }));

    emit("mockupUpdated");
  } catch (err: unknown) {
    mockupActionError.value = getApiErrorMessage(err, "Failed to set cover image.");
  } finally {
    isActionLoading.value = false;
  }
}

const mockupToDelete = ref<MockupAsset | null>(null);
const isDeletingMockup = ref(false);
const deleteMockupError = ref<string | null>(null);

function handleDeleteMockup(asset: MockupAsset): void {
  mockupToDelete.value = asset;
  deleteMockupError.value = null;
}

async function confirmDeleteMockup(): Promise<void> {
  if (!mockupToDelete.value) return;
  isDeletingMockup.value = true;
  deleteMockupError.value = null;
  try {
    await deleteMockup(props.workflow.id, mockupToDelete.value.id);
    mockupToDelete.value = null;
    emit("mockupUpdated");
  } catch (err: unknown) {
    deleteMockupError.value = getApiErrorMessage(err, "Failed to delete mockup.");
  } finally {
    isDeletingMockup.value = false;
  }
}

async function handleMoveMockup(asset: MockupAsset, direction: "up" | "down"): Promise<void> {
  const tabAssets = [...currentTabMockups.value];
  const idx = tabAssets.findIndex((a) => a.id === asset.id);
  if (idx < 0) return;

  const targetIdx = direction === "up" ? idx - 1 : idx + 1;
  if (targetIdx < 0 || targetIdx >= tabAssets.length) return;

  const temp = tabAssets[idx];
  tabAssets[idx] = tabAssets[targetIdx];
  tabAssets[targetIdx] = temp;

  const updatedTabItems = tabAssets.map((item, index) => ({
    ...item,
    provenance: { ...item.provenance, listing_order: index + 1 },
  }));

  localMockupAssets.value = localMockupAssets.value.map((a) => {
    const updated = updatedTabItems.find((u) => u.id === a.id);
    return updated ? { ...updated } : { ...a };
  });

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

    const data = await $fetch<MockupAsset[]>(
      `${apiBase}/api/v1/workflows/${props.workflow.id}/mockups/reorder`,
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
    mockupActionError.value = getApiErrorMessage(err, "Failed to reorder mockups.");
  } finally {
    isActionLoading.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Phase 7: PNG Production Pipeline Card -->
    <Card class="shadow-2xs border-border">
      <CardHeader class="pb-3 border-b border-border bg-secondary/30">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Icon name="lucide:file-image" class="size-5 text-primary" aria-hidden="true" />
            <div>
              <CardTitle class="text-base font-bold">Phase 7: Print-Ready PNG Production & Realistic Mockups</CardTitle>
              <CardDescription class="text-xs text-muted-foreground">
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
        <!-- Ready & Running States -->
        <ProductionStatusCard
          :state="workflow.state"
          :latest-production-job="latestProductionJob"
          :is-production-loading="isProductionLoading"
          :exact-slogan="approvedConcept?.prompts?.[0]?.exact_slogan"
          @start-production="emit('triggerProduction', false)"
        />

        <!-- Succeeded State (Master PNG, QA, & Mockup Gallery) -->
        <div v-if="latestProductionJob?.status === 'SUCCEEDED'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <!-- Left Column: Master PNG Preview & Actions -->
            <div class="lg:col-span-5 space-y-4">
              <MasterPngCard
                :master-image-url="masterImageUrl"
                :output-asset-id="latestProductionJob.output_asset_id"
                :render-nonce="renderNonce"
              />
            </div>

            <!-- Right Column: Automated QA Verification -->
            <div class="lg:col-span-7 space-y-4">
              <ProductionQaCard
                :qa-report="latestProductionJob.qa_report"
                :exact-slogan="approvedConcept?.prompts?.[0]?.exact_slogan"
              />
            </div>
          </div>

          <!-- Bottom: Realistic Multi-Mockup Gallery Grid -->
          <MockupGallery
            :available-tabs="availableProductTabs"
            :selected-tab="selectedMockupTab"
            :mockups-by-product="mockupsByProduct"
            :current-tab-mockups="currentTabMockups"
            :total-mockups-count="totalMockupsCount"
            :render-nonce="renderNonce"
            :is-action-loading="isActionLoading"
            :action-error="mockupActionError"
            @select-tab="(tab) => selectedMockupTab = tab"
            @open-add-mockup="openAddMockupModal"
            @adjust-placement="openAdjustMockupModal"
            @set-cover="handleSetCover"
            @delete="handleDeleteMockup"
            @move="handleMoveMockup"
          />
        </div>
      </CardContent>
    </Card>

    <!-- Custom Mockup Placement & Library Modal -->
    <WorkflowCustomMockupModal
      :open="showCustomMockupModal"
      :workflow-id="workflow.id"
      :product-type="selectedMockupTab"
      :master-asset-id="activeMasterAssetId || undefined"
      :master-image-url="masterImageUrl || undefined"
      :editing-asset="editingMockupAsset"
      @close="showCustomMockupModal = false"
      @mockup-created="handleCustomMockupCreated"
    />

    <!-- Delete Mockup Confirmation Dialog -->
    <DeleteConfirmModal
      :open="Boolean(mockupToDelete)"
      title="Delete Product Mockup?"
      description="Permanently delete this composited mockup from the listing."
      :item-name="mockupToDelete?.provenance?.template_name || getProductLabel(mockupToDelete?.provenance?.product_type || '')"
      :item-category="getProductLabel(mockupToDelete?.provenance?.product_type || '')"
      :image-url="mockupToDelete?.url || null"
      :is-deleting="isDeletingMockup"
      :error="deleteMockupError"
      confirm-text="Delete Mockup"
      @close="mockupToDelete = null"
      @confirm="confirmDeleteMockup"
    />
  </div>
</template>
