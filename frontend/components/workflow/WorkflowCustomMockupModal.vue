<script setup lang="ts">
import { ref, computed, watch } from "vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import type { MockupTemplateItem, MockupPlacement } from "~/types/mockup";
import { getProductLabel, getProductIconName, PRODUCT_PRESETS, normalizeProductKey } from "~/utils/mockupProducts";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";
import MockupTemplatePicker from "~/components/workflow/mockup-modal/MockupTemplatePicker.vue";
import MockupUploadDropzone from "~/components/workflow/mockup-modal/MockupUploadDropzone.vue";
import MockupPlacementCanvas from "~/components/workflow/mockup-modal/MockupPlacementCanvas.vue";
import MockupPlacementControls from "~/components/workflow/mockup-modal/MockupPlacementControls.vue";
import ImageCropperView from "~/components/ui/ImageCropperView.vue";
import DeleteConfirmModal from "~/components/ui/DeleteConfirmModal.vue";

export interface MockupAssetItem {
  id: string;
  workflow_id?: string;
  storage_key?: string;
  mime_type?: string;
  url?: string | null;
  width?: number | null;
  height?: number | null;
  template_id?: string | null;
  template_name?: string | null;
  provenance?: {
    phase?: number;
    asset_type?: string;
    product_type?: string;
    template_id?: string;
    template_name?: string;
    is_cover?: boolean;
    listing_order?: number;
    placement?: MockupPlacement;
  };
}

const props = defineProps<{
  open: boolean;
  workflowId: string;
  productType: string;
  masterImageUrl?: string | null;
  masterAssetId?: string | null;
  editingAsset?: MockupAssetItem | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (
    e: "mockupCreated",
    result: {
      mockup_url: string;
      asset_id?: string;
      product_type: string;
      template_id?: string;
      template_name?: string;
      is_cover?: boolean;
      listing_order?: number;
    }
  ): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

const activeSubTab = ref<"library" | "upload">("upload");
const canvasViewMode = ref<"edit" | "preview">("edit");
const templates = ref<MockupTemplateItem[]>([]);
const isFetchingTemplates = ref(false);
const selectedTemplateId = ref<string | null>(null);

// Upload state
const uploadedFile = ref<File | null>(null);
const uploadedPreviewUrl = ref<string | null>(null);
const templateName = ref("");
const saveToLibrary = ref(true);
const isCover = ref(false);

// Placement state
const leftPct = ref(25);
const topPct = ref(25);
const widthPct = ref(50);
const heightPct = ref(50);
const angleDeg = ref(0);
const blendMode = ref<"multiply" | "over" | "screen" | "overlay" | "darken" | "lighten">("multiply");

const isCompositing = ref(false);
const compositeError = ref<string | null>(null);

const activeTemplateImageUrl = computed<string | null>(() => {
  if (activeSubTab.value === "upload") {
    return uploadedPreviewUrl.value;
  }
  const tpl = templates.value.find((t) => t.id === selectedTemplateId.value);
  return tpl?.url || tpl?.preview_url || null;
});

function resetToDefaultPreset(): void {
  const norm = normalizeProductKey(props.productType);
  const preset = PRODUCT_PRESETS[norm] || PRODUCT_PRESETS.tshirt;
  leftPct.value = Math.round(preset.defaultPlacement.left_pct * 100);
  topPct.value = Math.round(preset.defaultPlacement.top_pct * 100);
  widthPct.value = Math.round(preset.defaultPlacement.width_pct * 100);
  heightPct.value = Math.round(preset.defaultPlacement.height_pct * 100);
  angleDeg.value = preset.defaultPlacement.angle_deg;
  blendMode.value = preset.defaultPlacement.blend_mode;
}

function centerHorizontal(): void {
  leftPct.value = Math.round(((100 - widthPct.value) / 2) * 10) / 10;
}

function centerBoth(): void {
  leftPct.value = Math.round(((100 - widthPct.value) / 2) * 10) / 10;
  topPct.value = Math.round(((100 - heightPct.value) / 2) * 10) / 10;
}

async function loadTemplatesForProduct(): Promise<void> {
  isFetchingTemplates.value = true;
  try {
    const norm = normalizeProductKey(props.productType);
    const res = await $fetch<MockupTemplateItem[]>(
      `${apiBase}/api/v1/mockup-templates?product_type=${norm}`,
      {
        headers: { Accept: "application/json" },
        credentials: "include",
      }
    );
    // Strict client-side filter by current product type
    templates.value = (res || []).filter(
      (t) => normalizeProductKey(t.product_type) === norm
    );
    if (templates.value.length > 0 && !selectedTemplateId.value) {
      handleSelectTemplate(templates.value[0]);
    }
  } catch {
    templates.value = [];
  } finally {
    isFetchingTemplates.value = false;
  }
}

function handleSelectTemplate(tpl: MockupTemplateItem): void {
  selectedTemplateId.value = tpl.id;
  templateName.value = tpl.name;
  if (tpl.placement) {
    leftPct.value = Math.round((tpl.placement.left_pct ?? 0.25) * 100);
    topPct.value = Math.round((tpl.placement.top_pct ?? 0.25) * 100);
    widthPct.value = Math.round((tpl.placement.width_pct ?? 0.5) * 100);
    heightPct.value = Math.round((tpl.placement.height_pct ?? 0.5) * 100);
    angleDeg.value = tpl.placement.angle_deg ?? 0;
    blendMode.value = tpl.placement.blend_mode || "multiply";
  }
}

const templateToDelete = ref<MockupTemplateItem | null>(null);
const isDeletingTemplate = ref(false);
const deleteTemplateError = ref<string | null>(null);

function handleDeleteTemplate(tplId: string): void {
  const found = templates.value.find((t) => t.id === tplId);
  templateToDelete.value = found || {
    id: tplId,
    name: "Mockup Template",
    product_type: props.productType,
  } as MockupTemplateItem;
  deleteTemplateError.value = null;
}

async function confirmDeleteTemplate(): Promise<void> {
  if (!templateToDelete.value) return;
  const tplId = templateToDelete.value.id;
  isDeletingTemplate.value = true;
  deleteTemplateError.value = null;
  try {
    await $fetch(`${apiBase}/api/v1/mockup-templates/${tplId}`, {
      method: "DELETE",
      headers: getCsrfHeaders(),
      credentials: "include",
    });
    templates.value = templates.value.filter((t) => t.id !== tplId);
    if (selectedTemplateId.value === tplId) {
      selectedTemplateId.value = templates.value[0]?.id || null;
    }
    templateToDelete.value = null;
  } catch (err: unknown) {
    deleteTemplateError.value = getApiErrorMessage(err, "Failed to delete template.");
  } finally {
    isDeletingTemplate.value = false;
  }
}

const isCroppingMode = ref(false);
const rawUploadImageUrl = ref<string | null>(null);

function handleFileSelected(file: File): void {
  uploadedFile.value = file;
  templateName.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
  const reader = new FileReader();
  reader.onload = (e) => {
    rawUploadImageUrl.value = e.target?.result as string;
    uploadedPreviewUrl.value = rawUploadImageUrl.value;
  };
  reader.readAsDataURL(file);
}

function handleCropComplete(result: {
  croppedFile: File;
  croppedUrl: string;
}): void {
  uploadedFile.value = result.croppedFile;
  uploadedPreviewUrl.value = result.croppedUrl;
  isCroppingMode.value = false;
}

function handleRemoveFile(): void {
  uploadedFile.value = null;
  uploadedPreviewUrl.value = null;
  rawUploadImageUrl.value = null;
  isCroppingMode.value = false;
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      compositeError.value = null;
      if (props.editingAsset) {
        // Editing existing mockup
        const prov = props.editingAsset.provenance;
        selectedTemplateId.value = prov?.template_id || null;
        templateName.value = prov?.template_name || "";
        isCover.value = Boolean(prov?.is_cover);
        if (prov?.placement) {
          leftPct.value = Math.round((prov.placement.left_pct ?? 0.25) * 100);
          topPct.value = Math.round((prov.placement.top_pct ?? 0.25) * 100);
          widthPct.value = Math.round((prov.placement.width_pct ?? 0.5) * 100);
          heightPct.value = Math.round((prov.placement.height_pct ?? 0.5) * 100);
          angleDeg.value = prov.placement.angle_deg ?? 0;
          blendMode.value = prov.placement.blend_mode || "multiply";
        }
        activeSubTab.value = "library";
        loadTemplatesForProduct();
      } else {
        // Fresh creation
        uploadedFile.value = null;
        uploadedPreviewUrl.value = null;
        selectedTemplateId.value = null;
        templateName.value = "";
        isCover.value = false;
        resetToDefaultPreset();
        loadTemplatesForProduct().then(() => {
          activeSubTab.value = templates.value.length > 0 ? "library" : "upload";
        });
      }
    }
  },
  { immediate: true }
);

async function handleGenerateMockup(): Promise<void> {
  if (!activeTemplateImageUrl.value) {
    compositeError.value = "Please select or upload a mockup photo template.";
    return;
  }

  isCompositing.value = true;
  compositeError.value = null;

  try {
    const headers = getCsrfHeaders();
    headers["Content-Type"] = "application/json";

    const payload: Record<string, any> = {
      workflow_id: props.workflowId,
      product_type: normalizeProductKey(props.productType),
      placement: {
        left_pct: leftPct.value / 100,
        top_pct: topPct.value / 100,
        width_pct: widthPct.value / 100,
        height_pct: heightPct.value / 100,
        angle_deg: angleDeg.value,
        blend_mode: blendMode.value,
      },
      is_cover: isCover.value,
      target_asset_id: props.editingAsset?.id || undefined,
      master_asset_id: props.masterAssetId || undefined,
    };

    if (activeSubTab.value === "library" && selectedTemplateId.value) {
      payload.template_id = selectedTemplateId.value;
      payload.template_name = templateName.value || undefined;
    } else if (uploadedPreviewUrl.value) {
      const b64Data = uploadedPreviewUrl.value.split(",")[1] || uploadedPreviewUrl.value;
      payload.template_image_base64 = b64Data;
      payload.template_name = templateName.value || `${getProductLabel(props.productType)} Template`;
      payload.save_as_template = saveToLibrary.value;
    }

    const res = await $fetch<{
      mockup_url: string;
      asset_id: string;
      product_type: string;
      template_id?: string;
      template_name?: string;
      is_cover?: boolean;
      listing_order?: number;
    }>(`${apiBase}/api/v1/mockup-templates/composite`, {
      method: "POST",
      headers,
      body: payload,
      credentials: "include",
    });

    emit("mockupCreated", res);
    emit("close");
  } catch (err: unknown) {
    compositeError.value = getApiErrorMessage(err, "Failed to create custom mockup.");
  } finally {
    isCompositing.value = false;
  }
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
    <div class="bg-white rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden border border-zinc-200 flex flex-col max-h-[92vh] animate-in fade-in zoom-in-95 duration-150">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
        <div class="flex items-center gap-3">
          <div class="size-9 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-200/60 flex items-center justify-center shadow-2xs">
            <Icon :name="getProductIconName(productType)" class="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-zinc-900 leading-tight">
              {{ editingAsset ? `Edit ${getProductLabel(productType)} Mockup` : `Add ${getProductLabel(productType)} Mockup` }}
            </h3>
            <p class="text-xs text-zinc-500">
              Position and blend your master transparent PNG onto realistic product photography
            </p>
          </div>
        </div>
        <button
          type="button"
          class="h-8 w-8 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Mode Selector Tabs (Library vs Upload New) -->
      <div class="px-6 pt-3 pb-2 border-b border-zinc-100 flex items-center justify-between bg-white">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
            :class="activeSubTab === 'library' ? 'bg-indigo-600 text-white shadow-2xs' : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200/70'"
            @click="activeSubTab = 'library'"
          >
            <Icon name="lucide:folder" class="size-3.5" aria-hidden="true" />
            <span>From Library</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full" :class="activeSubTab === 'library' ? 'bg-indigo-800 text-white' : 'bg-zinc-200 text-zinc-700'">
              {{ templates.length }}
            </span>
          </button>

          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
            :class="activeSubTab === 'upload' ? 'bg-indigo-600 text-white shadow-2xs' : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200/70'"
            @click="activeSubTab = 'upload'"
          >
            <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
            <span>Upload New Photo</span>
          </button>
        </div>

        <!-- View Mode Segment (Edit vs Preview) -->
        <div v-if="activeTemplateImageUrl" class="flex items-center gap-1 bg-zinc-100 p-0.5 rounded-lg text-xs">
          <button
            type="button"
            class="px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer"
            :class="canvasViewMode === 'edit' ? 'bg-white text-zinc-900 shadow-2xs font-bold' : 'text-zinc-500 hover:text-zinc-900'"
            @click="canvasViewMode = 'edit'"
          >
            Edit Box
          </button>
          <button
            type="button"
            class="px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer"
            :class="canvasViewMode === 'preview' ? 'bg-white text-zinc-900 shadow-2xs font-bold' : 'text-zinc-500 hover:text-zinc-900'"
            @click="canvasViewMode = 'preview'"
          >
            Preview Clean
          </button>
        </div>
      </div>

      <!-- Modal Body -->
      <div class="p-6 overflow-y-auto flex-1 space-y-4">
        <!-- Error Alert -->
        <Alert v-if="compositeError" variant="destructive" class="py-2.5">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <div>
            <AlertTitle class="text-xs font-bold">Error</AlertTitle>
            <AlertDescription class="text-xs">{{ compositeError }}</AlertDescription>
          </div>
        </Alert>

        <!-- Inline Cropper View when Cropping Mode is Active -->
        <div v-if="isCroppingMode" class="py-1">
          <ImageCropperView
            :image-url="rawUploadImageUrl || uploadedPreviewUrl"
            :file-name="uploadedFile?.name"
            @crop="handleCropComplete"
            @cancel="isCroppingMode = false"
          />
        </div>

        <!-- Normal Studio Workspace (when not cropping) -->
        <template v-else>
          <!-- Template Selector Section (Max 3 + Show More) -->
          <div v-if="activeSubTab === 'library'" class="pb-2 border-b border-zinc-100">
            <MockupTemplatePicker
              :templates="templates"
              :selected-template-id="selectedTemplateId"
              :product-label="getProductLabel(productType)"
              :is-fetching-templates="isFetchingTemplates"
              @select="handleSelectTemplate"
              @delete="handleDeleteTemplate"
              @switch-to-upload="activeSubTab = 'upload'"
            />
          </div>

          <!-- If Upload Mode: Show clean Dropzone with Crop option -->
          <div v-if="activeSubTab === 'upload'" class="py-2">
            <MockupUploadDropzone
              :product-label="getProductLabel(productType)"
              :has-file="Boolean(uploadedPreviewUrl)"
              :file-name="uploadedFile?.name"
              @file-selected="handleFileSelected"
              @remove-file="handleRemoveFile"
              @open-crop="isCroppingMode = true"
            />
          </div>

          <!-- 2-Column Studio Workspace -->
          <div v-if="activeTemplateImageUrl" class="grid grid-cols-1 md:grid-cols-12 gap-6 pt-1">
            <!-- Left Column: Interactive Placement Canvas -->
            <div class="md:col-span-6 space-y-3">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-zinc-800 flex items-center gap-1.5">
                  <Icon name="lucide:monitor" class="size-3.5 text-indigo-600" aria-hidden="true" />
                  <span>Placement Canvas Viewport</span>
                </span>
                <span class="text-[10px] text-zinc-400 font-mono">1:1 Aspect Frame</span>
              </div>

              <MockupPlacementCanvas
                :template-image-url="activeTemplateImageUrl"
                :master-image-url="masterImageUrl || null"
                :left-pct="leftPct"
                :top-pct="topPct"
                :width-pct="widthPct"
                :height-pct="heightPct"
                :angle-deg="angleDeg"
                :blend-mode="blendMode"
                :view-mode="canvasViewMode"
                @update:left-pct="(v) => leftPct = v"
                @update:top-pct="(v) => topPct = v"
                @update:width-pct="(v) => widthPct = v"
                @update:height-pct="(v) => heightPct = v"
                @update:angle-deg="(v) => angleDeg = v"
              />

              <p class="text-[11px] text-zinc-400 text-center">
                💡 Drag the bounding box to move · Drag bottom-right corner to resize
              </p>
            </div>

            <!-- Right Column: Fine Placement Controls & Metadata -->
            <div class="md:col-span-6 space-y-4">
              <MockupPlacementControls
                :left-pct="leftPct"
                :top-pct="topPct"
                :width-pct="widthPct"
                :height-pct="heightPct"
                :angle-deg="angleDeg"
                :blend-mode="blendMode"
                :template-name="templateName"
                :save-to-library="saveToLibrary"
                :is-cover="isCover"
                :is-compositing="isCompositing"
                :is-uploading-new="activeSubTab === 'upload'"
                @update:left-pct="(v) => leftPct = v"
                @update:top-pct="(v) => topPct = v"
                @update:width-pct="(v) => widthPct = v"
                @update:height-pct="(v) => heightPct = v"
                @update:angle-deg="(v) => angleDeg = v"
                @update:blend-mode="(v) => blendMode = v"
                @update:template-name="(v) => templateName = v"
                @update:save-to-library="(v) => saveToLibrary = v"
                @update:is-cover="(v) => isCover = v"
                @reset-preset="resetToDefaultPreset"
                @center-horizontal="centerHorizontal"
                @center-both="centerBoth"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Modal Footer (Hidden while in inline cropper view) -->
      <div v-if="!isCroppingMode" class="px-6 py-3 border-t border-zinc-100 flex items-center justify-between bg-zinc-50/50">
        <Button
          variant="outline"
          size="sm"
          class="text-xs cursor-pointer"
          :disabled="isCompositing"
          @click="emit('close')"
        >
          Cancel
        </Button>

        <Button
          variant="default"
          size="sm"
          class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold gap-2 shadow-xs cursor-pointer inline-flex items-center"
          :disabled="isCompositing || !activeTemplateImageUrl"
          @click="handleGenerateMockup"
        >
          <Icon v-if="isCompositing" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:wand-2" class="size-3.5" aria-hidden="true" />
          <span>{{ isCompositing ? "Generating Mockup..." : editingAsset ? "Save & Recomposite" : "Save Mockup" }}</span>
        </Button>
      </div>
    </div>

    <!-- Delete Template Confirmation Dialog -->
    <DeleteConfirmModal
      :open="Boolean(templateToDelete)"
      title="Delete Mockup Template?"
      description="Permanently delete this photo from your template library."
      :item-name="templateToDelete?.name"
      :item-category="getProductLabel(templateToDelete?.product_type || productType)"
      :image-url="templateToDelete?.url || templateToDelete?.preview_url || null"
      :is-deleting="isDeletingTemplate"
      :error="deleteTemplateError"
      confirm-text="Delete Permanently"
      @close="templateToDelete = null"
      @confirm="confirmDeleteTemplate"
    />
  </div>
</template>
