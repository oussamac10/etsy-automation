<script setup lang="ts">
import { ref, computed, watch } from "vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import type { MockupTemplateItem, MockupPlacement, MockupBlendMode } from "~/types/mockup";
import { getProductLabel, getProductIconName, PRODUCT_PRESETS, normalizeProductKey } from "~/utils/mockupProducts";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";
import MockupTemplatePicker from "~/components/workflow/mockup-modal/MockupTemplatePicker.vue";
import MockupUploadDropzone from "~/components/workflow/mockup-modal/MockupUploadDropzone.vue";
import MockupPlacementCanvas from "~/components/workflow/mockup-modal/MockupPlacementCanvas.vue";
import MockupPlacementControls from "~/components/workflow/mockup-modal/MockupPlacementControls.vue";
import ImageCropperView from "~/components/ui/ImageCropperView.vue";
import DeleteConfirmModal from "~/components/ui/DeleteConfirmModal.vue";
import { useArtworkVariants } from "~/composables/useArtworkVariants";

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
    template_id?: string | null;
    template_name?: string | null;
    is_cover?: boolean;
    listing_order?: number;
    placement?: MockupPlacement;
    placements?: MockupPlacement[];
    [key: string]: unknown;
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

const { variants, fetchVariants: fetchArtworkVariants } = useArtworkVariants();
const selectedArtworkSourceId = ref<string>("master");

const variantOptions = computed(() =>
  variants.value.map((v) => ({
    id: v.id,
    name: v.title,
    url: v.url || "",
  }))
);

// Multi-Placement State
const placements = ref<MockupPlacement[]>([
  {
    id: "zone-1",
    left_pct: 25,
    top_pct: 25,
    width_pct: 50,
    height_pct: 50,
    angle_deg: 0,
    blend_mode: "multiply",
    artwork_source_id: null,
  },
]);
const activePlacementIndex = ref(0);

// Active zone reactive bindings (kept in sync with activePlacementIndex)
const leftPct = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? z.left_pct : 25;
  },
  set: (val: number) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].left_pct = val;
    }
  },
});

const topPct = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? z.top_pct : 25;
  },
  set: (val: number) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].top_pct = val;
    }
  },
});

const widthPct = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? z.width_pct : 50;
  },
  set: (val: number) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].width_pct = val;
    }
  },
});

const heightPct = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? z.height_pct : 50;
  },
  set: (val: number) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].height_pct = val;
    }
  },
});

const angleDeg = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? (z.angle_deg || 0) : 0;
  },
  set: (val: number) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].angle_deg = val;
    }
  },
});

const blendMode = computed({
  get: () => {
    const z = placements.value[activePlacementIndex.value];
    return z ? (z.blend_mode || "multiply") : "multiply";
  },
  set: (val: MockupBlendMode | string) => {
    if (placements.value[activePlacementIndex.value]) {
      placements.value[activePlacementIndex.value].blend_mode = val;
    }
  },
});

const isModalLoading = ref(true);
const isCompositing = ref(false);
const compositeError = ref<string | null>(null);

const activeArtworkImageUrl = computed<string | null>(() => {
  if (selectedArtworkSourceId.value && selectedArtworkSourceId.value !== "master" && selectedArtworkSourceId.value !== props.masterAssetId) {
    const found = variants.value.find((v) => v.id === selectedArtworkSourceId.value);
    if (found?.url) return found.url;
  }
  return props.masterImageUrl || null;
});

const activeTemplateImageUrl = computed<string | null>(() => {
  if (activeSubTab.value === "upload") {
    return uploadedPreviewUrl.value;
  }
  const tpl = templates.value.find((t) => t.id === selectedTemplateId.value);
  return tpl?.url || tpl?.preview_url || null;
});

function addPrintZone(): void {
  const norm = normalizeProductKey(props.productType);
  const preset = PRODUCT_PRESETS[norm] || PRODUCT_PRESETS.tshirt;
  const count = placements.value.length;
  const offset = (count * 6) % 25;
  const newZone: MockupPlacement = {
    id: `zone-${Date.now()}-${count + 1}`,
    left_pct: Math.min(65, Math.round(preset.defaultPlacement.left_pct * 100) + offset),
    top_pct: Math.min(65, Math.round(preset.defaultPlacement.top_pct * 100) + offset),
    width_pct: Math.min(50, Math.round(preset.defaultPlacement.width_pct * 100)),
    height_pct: Math.min(50, Math.round(preset.defaultPlacement.height_pct * 100)),
    angle_deg: 0,
    blend_mode: preset.defaultPlacement.blend_mode,
    artwork_source_id: selectedArtworkSourceId.value !== "master" ? selectedArtworkSourceId.value : null,
  };
  placements.value.push(newZone);
  activePlacementIndex.value = placements.value.length - 1;
}

function duplicatePrintZone(index: number): void {
  const source = placements.value[index] || placements.value[0];
  if (!source) return;
  const newZone: MockupPlacement = {
    id: `zone-${Date.now()}`,
    left_pct: Math.min(70, Math.round((source.left_pct <= 1.0 ? source.left_pct * 100 : source.left_pct) + 5)),
    top_pct: Math.min(70, Math.round((source.top_pct <= 1.0 ? source.top_pct * 100 : source.top_pct) + 5)),
    width_pct: source.width_pct <= 1.0 ? source.width_pct * 100 : source.width_pct,
    height_pct: source.height_pct <= 1.0 ? source.height_pct * 100 : source.height_pct,
    angle_deg: source.angle_deg || 0,
    blend_mode: source.blend_mode || "multiply",
    artwork_source_id: source.artwork_source_id || null,
  };
  placements.value.push(newZone);
  activePlacementIndex.value = placements.value.length - 1;
}

function removePrintZone(index: number): void {
  if (placements.value.length <= 1) return;
  placements.value.splice(index, 1);
  if (activePlacementIndex.value >= placements.value.length) {
    activePlacementIndex.value = Math.max(0, placements.value.length - 1);
  }
}

function updateZoneArtworkSource(payload: { index: number; sourceId: string | null }): void {
  if (placements.value[payload.index]) {
    placements.value[payload.index].artwork_source_id = payload.sourceId;
  }
}

function resetToDefaultPreset(): void {
  const norm = normalizeProductKey(props.productType);
  const preset = PRODUCT_PRESETS[norm] || PRODUCT_PRESETS.tshirt;
  placements.value = [
    {
      id: "zone-1",
      left_pct: Math.round(preset.defaultPlacement.left_pct * 100),
      top_pct: Math.round(preset.defaultPlacement.top_pct * 100),
      width_pct: Math.round(preset.defaultPlacement.width_pct * 100),
      height_pct: Math.round(preset.defaultPlacement.height_pct * 100),
      angle_deg: preset.defaultPlacement.angle_deg || 0,
      blend_mode: preset.defaultPlacement.blend_mode || "multiply",
      artwork_source_id: null,
    },
  ];
  activePlacementIndex.value = 0;
}

function centerHorizontal(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.left_pct = Math.round(((100 - z.width_pct) / 2) * 10) / 10;
  }
}

function centerBoth(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.left_pct = Math.round(((100 - z.width_pct) / 2) * 10) / 10;
    z.top_pct = Math.round(((100 - z.height_pct) / 2) * 10) / 10;
  }
}

function applyFullCenterPreset(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.left_pct = 28;
    z.top_pct = 25;
    z.width_pct = 44;
    z.height_pct = 48;
  }
}

function applyChestPreset(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.left_pct = 52;
    z.top_pct = 26;
    z.width_pct = 22;
    z.height_pct = 24;
  }
}

function applySquarePreset(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.left_pct = 30;
    z.top_pct = 30;
    z.width_pct = 40;
    z.height_pct = 40;
  }
}

function rotateActiveLeft(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    let a = (z.angle_deg || 0) - 90;
    while (a < -180) a += 360;
    z.angle_deg = a;
  }
}

function rotateActiveRight(): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    let a = (z.angle_deg || 0) + 90;
    while (a > 180) a -= 360;
    z.angle_deg = a;
  }
}

function setActiveAngle(deg: number): void {
  const z = placements.value[activePlacementIndex.value];
  if (z) {
    z.angle_deg = deg;
  }
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
  if (tpl.placements && tpl.placements.length > 0) {
    placements.value = tpl.placements.map((p, idx) => ({
      id: p.id || `zone-${idx + 1}`,
      left_pct: Math.round((p.left_pct <= 1.0 ? p.left_pct : p.left_pct / 100) * 100),
      top_pct: Math.round((p.top_pct <= 1.0 ? p.top_pct : p.top_pct / 100) * 100),
      width_pct: Math.round((p.width_pct <= 1.0 ? p.width_pct : p.width_pct / 100) * 100),
      height_pct: Math.round((p.height_pct <= 1.0 ? p.height_pct : p.height_pct / 100) * 100),
      angle_deg: p.angle_deg || 0,
      blend_mode: p.blend_mode || "multiply",
      artwork_source_id: p.artwork_source_id || null,
    }));
  } else if (tpl.placement) {
    placements.value = [
      {
        id: "zone-1",
        left_pct: Math.round((tpl.placement.left_pct <= 1.0 ? tpl.placement.left_pct : tpl.placement.left_pct / 100) * 100),
        top_pct: Math.round((tpl.placement.top_pct <= 1.0 ? tpl.placement.top_pct : tpl.placement.top_pct / 100) * 100),
        width_pct: Math.round((tpl.placement.width_pct <= 1.0 ? tpl.placement.width_pct : tpl.placement.width_pct / 100) * 100),
        height_pct: Math.round((tpl.placement.height_pct <= 1.0 ? tpl.placement.height_pct : tpl.placement.height_pct / 100) * 100),
        angle_deg: tpl.placement.angle_deg || 0,
        blend_mode: tpl.placement.blend_mode || "multiply",
        artwork_source_id: tpl.placement.artwork_source_id || null,
      },
    ];
  }
  activePlacementIndex.value = 0;
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
  async (isOpen) => {
    if (isOpen) {
      isModalLoading.value = true;
      compositeError.value = null;
      templates.value = [];
      uploadedFile.value = null;
      uploadedPreviewUrl.value = null;
      rawUploadImageUrl.value = null;
      isCroppingMode.value = false;

      if (props.workflowId) {
        await fetchArtworkVariants(props.workflowId);
      }

      if (props.editingAsset) {
        // Editing existing mockup
        const prov = props.editingAsset.provenance;
        selectedTemplateId.value = prov?.template_id || null;
        templateName.value = prov?.template_name || "";
        isCover.value = Boolean(prov?.is_cover);

        // Retain the specific artwork source (variant or master) that this mockup was composited with
        if (
          prov?.source_asset_id &&
          String(prov.source_asset_id) !== props.masterAssetId &&
          variants.value.some((v) => v.id === String(prov.source_asset_id))
        ) {
          selectedArtworkSourceId.value = String(prov.source_asset_id);
        } else {
          selectedArtworkSourceId.value = "master";
        }

        if (prov?.placements && prov.placements.length > 0) {
          placements.value = prov.placements.map((p, idx) => ({
            id: p.id || `zone-${idx + 1}`,
            left_pct: Math.round((p.left_pct <= 1.0 ? p.left_pct : p.left_pct / 100) * 100),
            top_pct: Math.round((p.top_pct <= 1.0 ? p.top_pct : p.top_pct / 100) * 100),
            width_pct: Math.round((p.width_pct <= 1.0 ? p.width_pct : p.width_pct / 100) * 100),
            height_pct: Math.round((p.height_pct <= 1.0 ? p.height_pct : p.height_pct / 100) * 100),
            angle_deg: p.angle_deg || 0,
            blend_mode: p.blend_mode || "multiply",
            artwork_source_id: p.artwork_source_id || null,
          }));
        } else if (prov?.placement) {
          placements.value = [
            {
              id: "zone-1",
              left_pct: Math.round((prov.placement.left_pct <= 1.0 ? prov.placement.left_pct : prov.placement.left_pct / 100) * 100),
              top_pct: Math.round((prov.placement.top_pct <= 1.0 ? prov.placement.top_pct : prov.placement.top_pct / 100) * 100),
              width_pct: Math.round((prov.placement.width_pct <= 1.0 ? prov.placement.width_pct : prov.placement.width_pct / 100) * 100),
              height_pct: Math.round((prov.placement.height_pct <= 1.0 ? prov.placement.height_pct : prov.placement.height_pct / 100) * 100),
              angle_deg: prov.placement.angle_deg ?? 0,
              blend_mode: prov.placement.blend_mode || "multiply",
              artwork_source_id: prov.placement.artwork_source_id || null,
            },
          ];
        }
        activePlacementIndex.value = 0;
        activeSubTab.value = "library";
        await loadTemplatesForProduct();
        if (selectedTemplateId.value && !templates.value.some((t) => t.id === selectedTemplateId.value) && templates.value.length > 0) {
          selectedTemplateId.value = templates.value[0].id;
        }
      } else {
        // Fresh creation
        selectedArtworkSourceId.value = "master";
        selectedTemplateId.value = null;
        templateName.value = "";
        isCover.value = false;
        resetToDefaultPreset();
        await loadTemplatesForProduct();
        activeSubTab.value = templates.value.length > 0 ? "library" : "upload";
      }

      isModalLoading.value = false;
    } else {
      isModalLoading.value = false;
      templates.value = [];
      uploadedFile.value = null;
      uploadedPreviewUrl.value = null;
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
    const chosenArtworkId =
      selectedArtworkSourceId.value &&
      selectedArtworkSourceId.value !== "master" &&
      selectedArtworkSourceId.value !== props.masterAssetId
        ? selectedArtworkSourceId.value
        : props.masterAssetId || undefined;

    const normalizedPlacements = placements.value.map((p) => ({
      id: p.id,
      left_pct: p.left_pct / 100,
      top_pct: p.top_pct / 100,
      width_pct: p.width_pct / 100,
      height_pct: p.height_pct / 100,
      angle_deg: p.angle_deg || 0,
      blend_mode: p.blend_mode || "multiply",
      artwork_source_id: p.artwork_source_id || null,
    }));

    const primaryPlacement = normalizedPlacements[0] || {
      left_pct: 0.25,
      top_pct: 0.25,
      width_pct: 0.50,
      height_pct: 0.50,
      angle_deg: 0,
      blend_mode: "multiply",
    };

    const payload: Record<string, unknown> = {
      workflow_id: props.workflowId,
      product_type: normalizeProductKey(props.productType),
      placement: primaryPlacement,
      placements: normalizedPlacements,
      is_cover: isCover.value,
      target_asset_id: props.editingAsset?.id || undefined,
      master_asset_id: chosenArtworkId,
    };

    if (activeSubTab.value === "library" && selectedTemplateId.value) {
      payload.template_id = selectedTemplateId.value;
      payload.template_name = templateName.value || undefined;
    } else if (uploadedFile.value) {
      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const res = reader.result as string;
          resolve(res.includes(",") ? res.split(",")[1] : res);
        };
        reader.onerror = reject;
        reader.readAsDataURL(uploadedFile.value!);
      });
      payload.template_image_base64 = b64;
      payload.template_name = templateName.value || `${getProductLabel(props.productType)} Template`;
      payload.save_as_template = saveToLibrary.value;
    } else if (uploadedPreviewUrl.value) {
      let b64Data = uploadedPreviewUrl.value;
      if (b64Data.startsWith("blob:")) {
        const blobResp = await fetch(b64Data);
        const blob = await blobResp.blob();
        b64Data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            const res = reader.result as string;
            resolve(res.includes(",") ? res.split(",")[1] : res);
          };
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      } else if (b64Data.includes(",")) {
        b64Data = b64Data.split(",")[1];
      }
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

    emit("mockupCreated", {
      mockup_url: res.mockup_url,
      asset_id: res.asset_id,
      product_type: res.product_type,
      template_id: res.template_id,
      template_name: res.template_name,
      is_cover: res.is_cover,
      listing_order: res.listing_order,
    });
    emit("close");
  } catch (err: unknown) {
    compositeError.value = getApiErrorMessage(err, "Failed to composite custom mockup.");
  } finally {
    isCompositing.value = false;
  }
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs"
    @click.self="emit('close')"
  >
    <div
      class="bg-card text-card-foreground rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden border border-border flex flex-col max-h-[92vh] animate-in fade-in zoom-in-95 duration-150"
    >
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
        <div class="flex items-center gap-3">
          <div class="size-9 rounded-xl bg-secondary text-primary border border-border flex items-center justify-center shadow-2xs">
            <Icon :name="getProductIconName(productType)" class="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-foreground leading-tight">
              {{ editingAsset ? 'Edit Mockup Placement' : `Add ${getProductLabel(productType)} Mockup` }}
            </h3>
            <p class="text-xs text-muted-foreground">
              Position and blend your master transparent PNG onto realistic product photography
            </p>
          </div>
        </div>

        <button
          type="button"
          class="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Mode Selector Tabs (Library vs Upload New) -->
      <div class="px-6 pt-3 pb-2 border-b border-border flex items-center justify-between bg-card">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
            :class="[
              activeSubTab === 'library'
                ? 'bg-primary text-white shadow-2xs'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            ]"
            @click="activeSubTab = 'library'"
          >
            <Icon name="lucide:folder" class="size-3.5" aria-hidden="true" />
            <span>From Library</span>
            <span
              v-if="templates.length > 0"
              class="text-[10px] px-1.5 py-0.2 rounded-full"
              :class="activeSubTab === 'library' ? 'bg-primary-hover text-white' : 'bg-secondary text-secondary-foreground'"
            >
              {{ templates.length }}
            </span>
          </button>

          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
            :class="[
              activeSubTab === 'upload'
                ? 'bg-primary text-white shadow-2xs'
                : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
            ]"
            @click="activeSubTab = 'upload'"
          >
            <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
            <span>Upload New Photo</span>
          </button>
        </div>

        <!-- View Mode Segment (Edit vs Preview) -->
        <div class="flex items-center gap-1 bg-secondary/60 p-0.5 rounded-lg border border-border text-xs">
          <button
            type="button"
            class="px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer"
            :class="[
              canvasViewMode === 'edit'
                ? 'bg-card text-foreground shadow-2xs font-bold'
                : 'text-muted-foreground hover:text-foreground'
            ]"
            @click="canvasViewMode = 'edit'"
          >
            Edit Box
          </button>
          <button
            type="button"
            class="px-2.5 py-1 rounded-md font-semibold transition-colors cursor-pointer"
            :class="[
              canvasViewMode === 'preview'
                ? 'bg-card text-foreground shadow-2xs font-bold'
                : 'text-muted-foreground hover:text-foreground'
            ]"
            @click="canvasViewMode = 'preview'"
          >
            Clean Preview
          </button>
        </div>
      </div>

      <!-- Modal Body -->
      <div class="p-6 overflow-y-auto flex-1 space-y-4">
        <!-- Error Alert -->
        <Alert v-if="compositeError" variant="destructive" class="py-2.5">
          <Icon name="lucide:alert-circle" class="size-4" aria-hidden="true" />
          <AlertTitle>Mockup Generation Failed</AlertTitle>
          <AlertDescription class="text-xs">{{ compositeError }}</AlertDescription>
        </Alert>

        <!-- Inline Cropper View when Cropping Mode is Active -->
        <div v-if="isCroppingMode && rawUploadImageUrl" class="py-2">
          <ImageCropperView
            :image-url="rawUploadImageUrl"
            :aspect-ratio="null"
            @crop-complete="handleCropComplete"
            @cancel="isCroppingMode = false"
          />
        </div>

        <!-- Loading State Skeleton -->
        <div v-else-if="isModalLoading" class="py-8 space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-12 gap-6">
            <div class="md:col-span-6 aspect-square bg-slate-100 rounded-2xl border border-border/80 flex items-center justify-center">
              <Icon name="lucide:image" class="size-10 text-slate-300 animate-pulse" />
            </div>
            <div class="md:col-span-6 space-y-3">
              <div class="h-6 bg-slate-100 rounded-lg w-2/3 animate-pulse" />
              <div class="h-20 bg-slate-100 rounded-xl animate-pulse" />
              <div class="h-32 bg-slate-100 rounded-xl animate-pulse" />
            </div>
          </div>
        </div>

        <!-- Normal Studio Workspace -->
        <template v-else>
          <!-- Template Selector Section -->
          <div v-if="activeSubTab === 'library'" class="pb-2 border-b border-border">
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

          <!-- If Upload Mode -->
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

          <!-- Studio Workspace -->
          <div v-if="activeTemplateImageUrl" class="grid grid-cols-1 md:grid-cols-12 gap-6 pt-1">
            <div class="md:col-span-6 space-y-3">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Icon name="lucide:monitor" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Placement Canvas Viewport</span>
                </span>
                <span class="text-[10px] text-muted-foreground font-mono">1:1 Aspect Frame</span>
              </div>

              <!-- Print Zones Toolbar (Multi-Zone Placement Support) -->
              <div class="flex items-center justify-between p-2 rounded-xl bg-secondary/60 border border-border flex-wrap gap-2">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="text-xs font-bold text-foreground flex items-center gap-1 mr-1">
                    <Icon name="lucide:layers" class="size-3.5 text-primary" aria-hidden="true" />
                    <span>Print Zones ({{ placements.length }})</span>
                  </span>

                  <!-- Zone Pills -->
                  <div class="flex items-center gap-1 bg-card p-0.5 rounded-lg border border-border shadow-2xs">
                    <button
                      v-for="(zone, idx) in placements"
                      :key="zone.id || `left-zone-${idx}`"
                      type="button"
                      class="px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all cursor-pointer inline-flex items-center gap-1"
                      :class="[
                        activePlacementIndex === idx
                          ? 'bg-primary text-white shadow-2xs font-bold'
                          : 'text-secondary-foreground hover:text-foreground hover:bg-secondary'
                      ]"
                      @click="activePlacementIndex = idx"
                    >
                      <span>Zone {{ idx + 1 }}</span>
                      <span v-if="zone.angle_deg" class="text-[9px] opacity-80">({{ zone.angle_deg }}°)</span>
                    </button>
                  </div>
                </div>

                <!-- Zone Actions: Add, Duplicate, Delete -->
                <div class="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-7 text-xs px-2 gap-1 bg-card font-semibold cursor-pointer text-primary border-primary/30 hover:bg-primary/5"
                    title="Add another print zone"
                    @click="addPrintZone"
                  >
                    <Icon name="lucide:plus" class="size-3" aria-hidden="true" />
                    <span>Add Zone</span>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    class="h-7 text-xs px-2 gap-1 bg-card font-medium cursor-pointer text-muted-foreground hover:text-foreground"
                    title="Duplicate active zone"
                    @click="duplicatePrintZone(activePlacementIndex)"
                  >
                    <Icon name="lucide:copy" class="size-3" aria-hidden="true" />
                    <span class="hidden sm:inline">Duplicate</span>
                  </Button>

                  <Button
                    v-if="placements.length > 1"
                    variant="outline"
                    size="sm"
                    class="h-7 text-xs px-2 gap-1 bg-card font-medium cursor-pointer text-destructive hover:bg-destructive/10 hover:border-destructive/30 border-border"
                    title="Delete active zone"
                    @click="removePrintZone(activePlacementIndex)"
                  >
                    <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                  </Button>
                </div>
              </div>

              <div
                v-if="variants.length > 0"
                class="flex items-center justify-between p-2 rounded-xl bg-secondary/40 border border-border/80 text-xs"
              >
                <span class="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
                  <Icon name="lucide:palette" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Placed Artwork Graphic:</span>
                </span>
                <select
                  v-model="selectedArtworkSourceId"
                  class="h-7 text-xs px-2 py-0.5 rounded-lg border border-border bg-card font-medium text-foreground cursor-pointer focus:outline-hidden"
                >
                  <option value="master">Original Master PNG</option>
                  <option
                    v-for="v in variants"
                    :key="v.id"
                    :value="v.id"
                  >
                    {{ v.title }} {{ v.variant_status === 'approved' ? '✓ (Approved)' : '(Draft)' }}
                  </option>
                </select>
              </div>

              <MockupPlacementCanvas
                :template-image-url="activeTemplateImageUrl"
                :master-image-url="activeArtworkImageUrl || null"
                :placements="placements"
                :active-placement-index="activePlacementIndex"
                :variants="variantOptions"
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
                @update:active-placement-index="(idx) => activePlacementIndex = idx"
                @update-placements="(list) => placements = list"
              />

              <!-- Quick Placement & Rotation Segmented Toolbar Below Canvas -->
              <div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-secondary/40 border border-border flex-wrap">
                <!-- Alignment Presets -->
                <div class="flex items-center gap-1 bg-card p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                    title="Center artwork box"
                    @click="centerBoth"
                  >
                    <Icon name="lucide:crosshair" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Center</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                    title="Center horizontally"
                    @click="centerHorizontal"
                  >
                    <Icon name="lucide:align-horizontal-justify-center" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Center X</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                    title="Apply full center preset"
                    @click="applyFullCenterPreset"
                  >
                    <Icon name="lucide:maximize-2" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Full</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                    title="Apply left chest preset"
                    @click="applyChestPreset"
                  >
                    <Icon name="lucide:target" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Chest</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                    title="Apply square 1:1 preset"
                    @click="applySquarePreset"
                  >
                    <Icon name="lucide:square" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>1:1</span>
                  </button>
                </div>

                <!-- Rotation Quick Actions -->
                <div class="flex items-center gap-1 bg-card p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-0.5"
                    title="Rotate 90 degrees counter-clockwise"
                    @click="rotateActiveLeft"
                  >
                    <Icon name="lucide:rotate-ccw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>-90°</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-0.5"
                    title="Rotate 90 degrees clockwise"
                    @click="rotateActiveRight"
                  >
                    <Icon name="lucide:rotate-cw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>+90°</span>
                  </button>

                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md transition-all cursor-pointer inline-flex items-center gap-1"
                    title="Reset angle to 0°"
                    @click="setActiveAngle(0)"
                  >
                    <span>0°</span>
                  </button>
                </div>
              </div>

              <p class="text-[11px] text-muted-foreground text-center">
                💡 Drag bounding box to move · Drag stalk to rotate · Bottom-right to resize
              </p>
            </div>

            <!-- Right Column: Fine Placement Controls & Metadata -->
            <div class="md:col-span-6 space-y-4">
              <MockupPlacementControls
                :placements="placements"
                :active-placement-index="activePlacementIndex"
                :variants="variantOptions"
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
                @update:active-placement-index="(idx) => activePlacementIndex = idx"
                @update:template-name="(v) => templateName = v"
                @update:save-to-library="(v) => saveToLibrary = v"
                @update:is-cover="(v) => isCover = v"
                @add-zone="addPrintZone"
                @duplicate-zone="duplicatePrintZone"
                @remove-zone="removePrintZone"
                @update-zone-artwork-source="updateZoneArtworkSource"
                @reset-preset="resetToDefaultPreset"
                @center-horizontal="centerHorizontal"
                @center-both="centerBoth"
              />
            </div>
          </div>

          <!-- Empty template library warning if no templates exist -->
          <div v-else-if="activeSubTab === 'library' && templates.length === 0" class="py-12 text-center space-y-3 bg-secondary/20 rounded-2xl border border-dashed border-border">
            <div class="size-10 rounded-xl bg-secondary text-muted-foreground flex items-center justify-center mx-auto">
              <Icon name="lucide:image" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <p class="text-xs font-bold text-foreground">No {{ getProductLabel(productType) }} templates found</p>
              <p class="text-[11px] text-muted-foreground mt-0.5">Upload a blank mockup photo to place your artwork</p>
            </div>
            <Button size="sm" variant="default" class="text-xs font-bold gap-1.5 cursor-pointer" @click="activeSubTab = 'upload'">
              <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
              <span>Upload New Template</span>
            </Button>
          </div>
        </template>
      </div>

      <!-- Modal Footer (Hidden while in inline cropper view) -->
      <div v-if="!isCroppingMode" class="px-6 py-3 border-t border-border flex items-center justify-between bg-secondary/30">
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
          class="font-bold gap-2 shadow-xs cursor-pointer inline-flex items-center"
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
