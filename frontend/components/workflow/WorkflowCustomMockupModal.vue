<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import Button from "~/components/ui/Button.vue";
import { getProductIcon } from "~/config/icons";

interface MockupTemplateItem {
  id: string;
  name: string;
  product_type: string;
  url: string;
  placement: {
    left_pct: number;
    top_pct: number;
    width_pct: number;
    height_pct: number;
    angle_deg: number;
    blend_mode: string;
  };
  created_at: string;
  is_custom: boolean;
}

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
    placement?: {
      left_pct?: number;
      top_pct?: number;
      width_pct?: number;
      height_pct?: number;
      angle_deg?: number;
      blend_mode?: string;
    };
  };
}

const props = defineProps<{
  open: boolean;
  workflowId: string;
  productType: string;
  masterImageUrl?: string | null;
  editingAsset?: MockupAssetItem | null;
}>();

const emit = defineEmits<{
  (e: "update:open", val: boolean): void;
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
const apiBase = config.public.apiBase;

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

// Placement state
const leftPct = ref(25);
const topPct = ref(25);
const widthPct = ref(50);
const heightPct = ref(50);
const angleDeg = ref(0);
const blendMode = ref<"multiply" | "over">("multiply");

// Drag & Interaction refs
const interactiveCanvasRef = ref<HTMLDivElement | null>(null);
const isDraggingArtwork = ref(false);
const isResizingArtwork = ref(false);
let dragStartX = 0;
let dragStartY = 0;
let initialLeft = 25;
let initialTop = 25;
let initialWidth = 50;
let initialHeight = 50;

const isCompositing = ref(false);
const compositeError = ref<string | null>(null);

function getMockupDisplayName(type: string): string {
  if (!type) return "Product";
  const clean = type.toLowerCase().trim();
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

const activeTemplateImageUrl = computed<string | null>(() => {
  if (activeSubTab.value === "upload") {
    return uploadedPreviewUrl.value;
  }
  const found = templates.value.find((t) => t.id === selectedTemplateId.value);
  return found?.url ?? null;
});

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(",") ? result.split(",")[1] : result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function applyDefaultPresetForProduct(product: string): void {
  const clean = product ? product.toLowerCase().trim() : "";
  if (clean.includes("mug") || clean.includes("ceramic")) {
    leftPct.value = 32;
    topPct.value = 32;
    widthPct.value = 36;
    heightPct.value = 38;
    blendMode.value = "over";
  } else if (clean.includes("tumbler")) {
    leftPct.value = 30;
    topPct.value = 28;
    widthPct.value = 40;
    heightPct.value = 48;
    blendMode.value = "over";
  } else if (clean.includes("poster") || clean.includes("wall_art")) {
    leftPct.value = 20;
    topPct.value = 20;
    widthPct.value = 60;
    heightPct.value = 60;
    blendMode.value = "over";
  } else if (clean.includes("tote") || clean.includes("bag")) {
    leftPct.value = 26;
    topPct.value = 36;
    widthPct.value = 48;
    heightPct.value = 46;
    blendMode.value = "multiply";
  } else if (clean.includes("sweat") || clean.includes("hoodie") || clean.includes("crewneck")) {
    leftPct.value = 28;
    topPct.value = 26;
    widthPct.value = 44;
    heightPct.value = 46;
    blendMode.value = "multiply";
  } else {
    // Default T-shirt / apparel
    leftPct.value = 28;
    topPct.value = 25;
    widthPct.value = 44;
    heightPct.value = 48;
    blendMode.value = "multiply";
  }
  angleDeg.value = 0;
}

// Reset or load state when opening, switching product, or editing existing mockup
watch(
  () => [props.open, props.productType, props.editingAsset],
  ([isOpen]) => {
    if (isOpen) {
      compositeError.value = null;
      uploadedFile.value = null;
      uploadedPreviewUrl.value = null;
      selectedTemplateId.value = null;
      templateName.value = "";
      canvasViewMode.value = "edit";

      if (props.editingAsset) {
        templateName.value =
          props.editingAsset.provenance?.template_name ||
          props.editingAsset.template_name ||
          `${getMockupDisplayName(props.productType)} Mockup`;

        const placement = props.editingAsset.provenance?.placement;
        if (placement) {
          leftPct.value = Math.round((placement.left_pct ?? 0.25) * (placement.left_pct! <= 1.0 ? 100 : 1));
          topPct.value = Math.round((placement.top_pct ?? 0.25) * (placement.top_pct! <= 1.0 ? 100 : 1));
          widthPct.value = Math.round((placement.width_pct ?? 0.50) * (placement.width_pct! <= 1.0 ? 100 : 1));
          heightPct.value = Math.round((placement.height_pct ?? 0.50) * (placement.height_pct! <= 1.0 ? 100 : 1));
          angleDeg.value = placement.angle_deg ?? 0;
          blendMode.value = (placement.blend_mode as "multiply" | "over") || "multiply";
        }

        if (props.editingAsset.provenance?.template_id) {
          selectedTemplateId.value = props.editingAsset.provenance.template_id;
          activeSubTab.value = "library";
        }
      } else {
        applyDefaultPresetForProduct(props.productType);
      }

      fetchTemplates();
    }
  },
  { immediate: true }
);

async function fetchTemplates(): Promise<void> {
  isFetchingTemplates.value = true;
  try {
    const data = await $fetch<{ items: MockupTemplateItem[] } | MockupTemplateItem[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates?product_type=${props.productType}`,
      { credentials: "include" }
    );
    if (Array.isArray(data)) {
      templates.value = data;
    } else {
      templates.value = data.items || [];
    }
    if (templates.value.length > 0 && !selectedTemplateId.value && activeSubTab.value === "library") {
      selectLibraryTemplate(templates.value[0]);
    }
  } catch (err) {
    console.error("Failed to load mockup templates", err);
  } finally {
    isFetchingTemplates.value = false;
  }
}

function selectLibraryTemplate(tpl: MockupTemplateItem): void {
  selectedTemplateId.value = tpl.id;
  leftPct.value = Math.round(tpl.placement.left_pct * (tpl.placement.left_pct <= 1.0 ? 100 : 1));
  topPct.value = Math.round(tpl.placement.top_pct * (tpl.placement.top_pct <= 1.0 ? 100 : 1));
  widthPct.value = Math.round(tpl.placement.width_pct * (tpl.placement.width_pct <= 1.0 ? 100 : 1));
  heightPct.value = Math.round(tpl.placement.height_pct * (tpl.placement.height_pct <= 1.0 ? 100 : 1));
  angleDeg.value = tpl.placement.angle_deg ?? 0;
  blendMode.value = (tpl.placement.blend_mode as "multiply" | "over") || "multiply";
}

function handleFileSelect(e: Event): void {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    processFile(input.files[0]);
  }
}

function handleDrop(e: DragEvent): void {
  e.preventDefault();
  if (e.dataTransfer?.files && e.dataTransfer.files[0]) {
    processFile(e.dataTransfer.files[0]);
  }
}

function processFile(file: File): void {
  if (!file.type.startsWith("image/")) {
    compositeError.value = "Please upload an image file (PNG, JPG, or WebP).";
    return;
  }
  uploadedFile.value = file;
  uploadedPreviewUrl.value = URL.createObjectURL(file);
  compositeError.value = null;
  if (!templateName.value) {
    const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
    templateName.value = cleanName.charAt(0).toUpperCase() + cleanName.slice(1);
  }
}

// Quick alignment presets
function centerHorizontally(): void {
  leftPct.value = Math.max(0, Math.round((100 - widthPct.value) / 2));
}

function centerVertically(): void {
  topPct.value = Math.max(0, Math.round((100 - heightPct.value) / 2));
}

function applyChestPreset(): void {
  widthPct.value = 25;
  heightPct.value = 25;
  leftPct.value = 55;
  topPct.value = 28;
}

function applyFullCenterPreset(): void {
  widthPct.value = 46;
  heightPct.value = 46;
  centerHorizontally();
  topPct.value = 24;
}

// Pointer Event Handlers for Dragging & Resizing
function onArtworkPointerDown(e: PointerEvent): void {
  if (canvasViewMode.value !== "edit") return;
  e.stopPropagation();
  e.preventDefault();
  isDraggingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialLeft = leftPct.value;
  initialTop = topPct.value;

  window.addEventListener("pointermove", onWindowPointerMove);
  window.addEventListener("pointerup", onWindowPointerUp);
}

function onResizeHandlePointerDown(e: PointerEvent): void {
  if (canvasViewMode.value !== "edit") return;
  e.stopPropagation();
  e.preventDefault();
  isResizingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialWidth = widthPct.value;
  initialHeight = heightPct.value;

  window.addEventListener("pointermove", onWindowPointerMove);
  window.addEventListener("pointerup", onWindowPointerUp);
}

function onWindowPointerMove(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  const deltaX = e.clientX - dragStartX;
  const deltaY = e.clientY - dragStartY;

  const deltaPctX = (deltaX / rect.width) * 100;
  const deltaPctY = (deltaY / rect.height) * 100;

  if (isDraggingArtwork.value) {
    let newLeft = Math.round(initialLeft + deltaPctX);
    let newTop = Math.round(initialTop + deltaPctY);

    newLeft = Math.max(0, Math.min(100 - widthPct.value, newLeft));
    newTop = Math.max(0, Math.min(100 - heightPct.value, newTop));

    leftPct.value = newLeft;
    topPct.value = newTop;
  } else if (isResizingArtwork.value) {
    let newWidth = Math.round(initialWidth + deltaPctX);
    let newHeight = Math.round(initialHeight + deltaPctY);

    newWidth = Math.max(10, Math.min(100 - leftPct.value, newWidth));
    newHeight = Math.max(10, Math.min(100 - topPct.value, newHeight));

    widthPct.value = newWidth;
    heightPct.value = newHeight;
  }
}

function onWindowPointerUp(): void {
  isDraggingArtwork.value = false;
  isResizingArtwork.value = false;
  window.removeEventListener("pointermove", onWindowPointerMove);
  window.removeEventListener("pointerup", onWindowPointerUp);
}

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("pointermove", onWindowPointerMove);
    window.removeEventListener("pointerup", onWindowPointerUp);
  }
});

async function handleComposite(): Promise<void> {
  isCompositing.value = true;
  compositeError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (csrf) headers["x-csrf-token"] = csrf;

    let templateBase64: string | null = null;
    if (activeSubTab.value === "upload") {
      if (!uploadedFile.value) {
        compositeError.value = "Please upload a mockup photo first.";
        isCompositing.value = false;
        return;
      }
      templateBase64 = await fileToBase64(uploadedFile.value);
    } else {
      if (!selectedTemplateId.value) {
        compositeError.value = "Please select a template from your library.";
        isCompositing.value = false;
        return;
      }
    }

    const payload = {
      workflow_id: props.workflowId,
      product_type: props.productType,
      template_id: activeSubTab.value === "library" ? selectedTemplateId.value : undefined,
      template_image_base64: templateBase64 || undefined,
      template_name: templateName.value || `${getMockupDisplayName(props.productType)} Mockup`,
      save_as_template: saveToLibrary.value,
      target_asset_id: props.editingAsset?.id || undefined,
      placement: {
        left_pct: leftPct.value / 100,
        top_pct: topPct.value / 100,
        width_pct: widthPct.value / 100,
        height_pct: heightPct.value / 100,
        angle_deg: angleDeg.value,
        blend_mode: blendMode.value,
      },
    };

    const result = await $fetch<{
      mockup_url: string;
      asset_id?: string;
      product_type: string;
      template_id?: string;
      template_name?: string;
      is_cover?: boolean;
      listing_order?: number;
    }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates/composite`,
      {
        method: "POST",
        headers,
        body: payload,
        credentials: "include",
      }
    );

    emit("mockupCreated", result);
    emit("update:open", false);
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    compositeError.value = errorObj.data?.detail || errorObj.message || "Failed to composite mockup. Please try again.";
  } finally {
    isCompositing.value = false;
  }
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-zinc-950/70 backdrop-blur-xs animate-in fade-in duration-200"
  >
    <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-4xl w-full overflow-hidden flex flex-col max-h-[92vh]">
      <!-- Header -->
      <div class="px-5 py-3.5 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/70">
        <div class="flex items-center gap-3">
          <div class="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Icon name="lucide:layers" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-sm font-bold text-zinc-900">
                {{ editingAsset ? 'Adjust Mockup Placement' : 'Custom Mockup Placer' }}
              </h3>
              <span class="text-xs px-2 py-0.5 rounded-full font-semibold bg-indigo-100 text-indigo-800 inline-flex items-center gap-1">
                <Icon :name="getProductIcon(productType)" class="size-3 text-indigo-700" aria-hidden="true" />
                <span>{{ getMockupDisplayName(productType) }}</span>
              </span>
            </div>
            <p class="text-[11px] text-zinc-500">Position, scale, and blend your master design on {{ getMockupDisplayName(productType) }}</p>
          </div>
        </div>
        <button
          type="button"
          class="h-8 w-8 rounded-lg hover:bg-zinc-200/70 text-zinc-400 hover:text-zinc-700 flex items-center justify-center transition-colors cursor-pointer"
          aria-label="Close modal"
          @click="emit('update:open', false)"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Main Body: 2-Column Split Layout -->
      <div class="p-5 overflow-y-auto lg:overflow-y-hidden max-h-[calc(92vh-115px)]">
        <!-- Error Alert -->
        <div v-if="compositeError" class="p-2.5 mb-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 font-medium">
          {{ compositeError }}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          <!-- LEFT COLUMN (7 cols): Interactive Visual Canvas -->
          <div class="lg:col-span-7 space-y-2.5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <Icon
                  :name="canvasViewMode === 'edit' ? 'lucide:move' : 'lucide:eye'"
                  class="size-3.5"
                  :class="canvasViewMode === 'edit' ? 'text-indigo-600' : 'text-emerald-600'"
                  aria-hidden="true"
                />
                <span class="text-xs font-bold text-zinc-900">
                  {{ canvasViewMode === 'edit' ? 'Interactive Placement Canvas' : 'Realistic Mockup Preview' }}
                </span>
              </div>

              <!-- View Switcher -->
              <div class="flex items-center gap-1 bg-zinc-100 p-0.5 rounded-lg border border-zinc-200 text-[11px]">
                <button
                  type="button"
                  class="font-semibold px-2 py-0.5 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                  :class="canvasViewMode === 'edit' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                  @click="canvasViewMode = 'edit'"
                >
                  <Icon name="lucide:sliders-horizontal" class="size-3" aria-hidden="true" />
                  <span>Edit</span>
                </button>
                <button
                  type="button"
                  class="font-semibold px-2 py-0.5 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                  :class="canvasViewMode === 'preview' ? 'bg-indigo-600 text-white shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                  @click="canvasViewMode = 'preview'"
                >
                  <Icon name="lucide:eye" class="size-3" aria-hidden="true" />
                  <span>Realistic</span>
                </button>
              </div>
            </div>

            <!-- Canvas Viewport -->
            <div
              ref="interactiveCanvasRef"
              class="relative aspect-square max-h-[305px] w-full mx-auto bg-zinc-900/5 rounded-xl border border-zinc-200 overflow-hidden select-none touch-none flex items-center justify-center shadow-inner"
            >
              <!-- Template Background -->
              <img
                v-if="activeTemplateImageUrl"
                :src="activeTemplateImageUrl"
                alt="Mockup Template"
                class="w-full h-full object-contain pointer-events-none"
              />
              <div v-else class="text-center p-6 text-zinc-400 space-y-2">
                <Icon name="lucide:image" class="size-10 mx-auto text-zinc-300" aria-hidden="true" />
                <p class="text-xs font-medium">Upload or select a photo on the right to start</p>
              </div>

              <!-- Alignment Crosshairs (Edit mode) -->
              <template v-if="canvasViewMode === 'edit' && activeTemplateImageUrl">
                <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-indigo-400/30 pointer-events-none" />
                <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-indigo-400/30 pointer-events-none" />
              </template>

              <!-- EDIT MODE: Draggable & Resizable Box -->
              <div
                v-if="canvasViewMode === 'edit' && activeTemplateImageUrl"
                class="absolute border-2 border-indigo-600 bg-indigo-500/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-xs transition-shadow shadow-md hover:ring-2 hover:ring-indigo-400/50"
                :style="{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }"
                @pointerdown="onArtworkPointerDown"
              >
                <!-- Pill Coordinates -->
                <div class="absolute -top-6 left-1/2 -translate-x-1/2 px-1.5 py-0.2 bg-zinc-900/90 text-white rounded text-[8px] font-mono whitespace-nowrap pointer-events-none shadow-xs">
                  {{ leftPct }}%, {{ topPct }}% ({{ widthPct }}×{{ heightPct }}%)
                </div>

                <!-- Artwork Preview -->
                <img
                  v-if="masterImageUrl"
                  :src="masterImageUrl"
                  alt="Artwork"
                  class="w-full h-full object-contain pointer-events-none select-none drop-shadow-xs"
                  :class="blendMode === 'multiply' ? 'mix-blend-multiply' : 'mix-blend-normal'"
                />
                <div v-else class="text-center p-1 pointer-events-none">
                  <span class="text-[9px] font-bold text-indigo-900 block leading-tight">Print Area</span>
                </div>

                <!-- Resize Handle -->
                <div
                  class="absolute -bottom-1.5 -right-1.5 h-3.5 w-3.5 bg-indigo-600 border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                  title="Drag to resize print area"
                  @pointerdown="onResizeHandlePointerDown"
                >
                  <Icon name="lucide:maximize-2" class="size-1.5 text-white" aria-hidden="true" />
                </div>
              </div>

              <!-- PREVIEW MODE: Composite Preview -->
              <div
                v-else-if="masterImageUrl && activeTemplateImageUrl"
                class="absolute pointer-events-none flex items-center justify-center"
                :style="{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }"
              >
                <img
                  :src="masterImageUrl"
                  alt="Artwork Preview"
                  class="w-full h-full object-contain pointer-events-none select-none"
                  :class="blendMode === 'multiply' ? 'mix-blend-multiply opacity-95' : 'mix-blend-normal opacity-95'"
                  :style="{
                    filter: blendMode === 'multiply' ? 'contrast(1.05) brightness(0.98)' : 'drop-shadow(0 2px 4px rgba(0,0,0,0.12))'
                  }"
                />
              </div>
            </div>

            <!-- Canvas Helpers / Quick Align -->
            <div v-if="canvasViewMode === 'edit' && activeTemplateImageUrl" class="flex flex-wrap items-center justify-between gap-1.5 text-[11px] pt-0.5">
              <div class="flex items-center gap-1">
                <span class="text-zinc-400 font-medium">Align:</span>
                <button
                  type="button"
                  class="px-2 py-0.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded font-medium inline-flex items-center gap-1 transition-colors cursor-pointer"
                  @click="centerHorizontally"
                >
                  <Icon name="lucide:align-center" class="size-2.5" aria-hidden="true" />
                  <span>Center H</span>
                </button>
                <button
                  type="button"
                  class="px-2 py-0.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded font-medium inline-flex items-center gap-1 transition-colors cursor-pointer"
                  @click="centerVertically"
                >
                  <Icon name="lucide:align-center" class="size-2.5 rotate-90" aria-hidden="true" />
                  <span>Center V</span>
                </button>
              </div>

              <div class="flex items-center gap-1">
                <span class="text-zinc-400 font-medium">Presets:</span>
                <button
                  type="button"
                  class="px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded font-medium transition-colors cursor-pointer border border-indigo-200"
                  @click="applyChestPreset"
                >
                  Chest Logo
                </button>
                <button
                  type="button"
                  class="px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded font-medium transition-colors cursor-pointer border border-indigo-200"
                  @click="applyFullCenterPreset"
                >
                  Full Center
                </button>
              </div>
            </div>
          </div>

          <!-- RIGHT COLUMN (5 cols): Photo Source & Precision Sliders -->
          <div class="lg:col-span-5 space-y-3.5">
            <!-- 1. Source Tab Selector -->
            <div class="p-1 bg-zinc-100 rounded-lg flex items-center gap-1">
              <button
                type="button"
                class="flex-1 text-xs font-semibold py-1.5 rounded-md transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                :class="activeSubTab === 'upload' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                @click="activeSubTab = 'upload'"
              >
                <Icon name="lucide:upload" class="size-3" aria-hidden="true" />
                <span>Upload Photo</span>
              </button>

              <button
                type="button"
                class="flex-1 text-xs font-semibold py-1.5 rounded-md transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                :class="activeSubTab === 'library' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                @click="activeSubTab = 'library'"
              >
                <Icon name="lucide:bookmark-plus" class="size-3" aria-hidden="true" />
                <span>Library ({{ templates.length }})</span>
              </button>
            </div>

            <!-- Upload Mode -->
            <div v-if="activeSubTab === 'upload'" class="space-y-2.5">
              <!-- Upload input dropzone -->
              <div
                v-if="!uploadedPreviewUrl"
                class="border border-dashed border-zinc-300 hover:border-indigo-500 rounded-xl p-3.5 text-center cursor-pointer transition-colors bg-zinc-50/50"
                @dragover.prevent
                @drop="handleDrop"
                @click="($refs.fileInput as HTMLInputElement)?.click()"
              >
                <input
                  ref="fileInput"
                  type="file"
                  accept="image/png, image/jpeg, image/webp"
                  class="hidden"
                  @change="handleFileSelect"
                >
                <Icon name="lucide:upload" class="size-5 mx-auto text-indigo-600 mb-1" aria-hidden="true" />
                <span class="text-xs font-semibold text-zinc-800 block">Click to upload photo</span>
                <span class="text-[10px] text-zinc-400 block mt-0.5">JPEG, PNG, WebP (up to 35MB)</span>
              </div>

              <!-- Uploaded thumbnail + name input -->
              <div v-else class="space-y-2 p-2.5 rounded-xl bg-zinc-50 border border-zinc-200">
                <div class="flex items-center gap-2">
                  <div class="h-10 w-10 rounded-lg bg-white border border-zinc-200 overflow-hidden shrink-0 flex items-center justify-center p-0.5">
                    <img :src="uploadedPreviewUrl" alt="Uploaded Photo" class="h-full w-full object-cover rounded" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <label class="block text-[9px] font-bold text-zinc-500 uppercase tracking-wider mb-0.5">Mockup Display Name</label>
                    <input
                      v-model="templateName"
                      type="text"
                      class="w-full text-xs px-2 py-1 rounded border border-zinc-200 bg-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                      :placeholder="`e.g. Bella Canvas ${getMockupDisplayName(productType)} Flatlay`"
                    >
                  </div>
                </div>

                <div class="flex items-center justify-between text-[10px] pt-1 border-t border-zinc-100">
                  <label class="flex items-center gap-1.5 cursor-pointer text-zinc-700">
                    <input
                      v-model="saveToLibrary"
                      type="checkbox"
                      class="h-3 w-3 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    >
                    <span>Save to library</span>
                  </label>

                  <button
                    type="button"
                    class="text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
                    @click="uploadedPreviewUrl = null; uploadedFile = null"
                  >
                    Change Photo
                  </button>
                </div>
              </div>
            </div>

            <!-- Library Mode (Clean compact grid with NO internal scroll) -->
            <div v-else class="space-y-1.5">
              <div v-if="templates.length === 0" class="text-center py-3 text-zinc-400 text-xs bg-zinc-50 rounded-xl border border-dashed border-zinc-200">
                No saved templates for {{ getMockupDisplayName(productType) }}. Use Upload tab to add one.
              </div>

              <div v-else class="grid grid-cols-3 gap-2">
                <button
                  v-for="tpl in templates"
                  :key="tpl.id"
                  type="button"
                  class="border rounded-xl p-1.5 text-left transition-all cursor-pointer relative group"
                  :class="selectedTemplateId === tpl.id ? 'border-indigo-600 ring-2 ring-indigo-500/30 bg-indigo-50/60 shadow-2xs' : 'border-zinc-200 hover:border-zinc-300 bg-white'"
                  @click="selectLibraryTemplate(tpl)"
                >
                  <div class="aspect-square bg-zinc-100 rounded-lg overflow-hidden border border-zinc-100 mb-1 flex items-center justify-center">
                    <img :src="tpl.url" :alt="tpl.name" class="object-cover w-full h-full" />
                  </div>
                  <p class="text-[10px] font-bold text-zinc-800 truncate text-center" :title="tpl.name">{{ tpl.name }}</p>
                </button>
              </div>
            </div>

            <!-- 2. Blend Mode Selector -->
            <div class="p-2 bg-zinc-50 rounded-xl border border-zinc-200 space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold text-zinc-700 flex items-center gap-1">
                  <Icon name="lucide:sparkles" class="size-3 text-indigo-600" aria-hidden="true" />
                  <span>Blend Mode</span>
                </span>
                <span class="text-[9px] text-zinc-400">{{ blendMode === 'multiply' ? 'Natural Shadows' : 'Solid Opaque' }}</span>
              </div>

              <div class="grid grid-cols-2 gap-1 text-xs">
                <button
                  type="button"
                  class="py-1 px-1.5 rounded-md font-semibold text-[10px] transition-all cursor-pointer border text-center truncate"
                  :class="blendMode === 'multiply' ? 'bg-indigo-600 text-white border-indigo-600 shadow-2xs' : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100'"
                  @click="blendMode = 'multiply'"
                >
                  Multiply (Light)
                </button>
                <button
                  type="button"
                  class="py-1 px-1.5 rounded-md font-semibold text-[10px] transition-all cursor-pointer border text-center truncate"
                  :class="blendMode === 'over' ? 'bg-indigo-600 text-white border-indigo-600 shadow-2xs' : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100'"
                  @click="blendMode = 'over'"
                >
                  Opaque (Dark)
                </button>
              </div>
            </div>

            <!-- 3. Compact Precision Sliders (2x2 Grid) -->
            <div v-if="canvasViewMode === 'edit'" class="p-2.5 bg-zinc-50 rounded-xl border border-zinc-200 space-y-1.5 text-xs">
              <span class="text-[10px] font-bold text-zinc-700 block uppercase tracking-wider">Position & Dimensions</span>

              <div class="grid grid-cols-2 gap-x-2.5 gap-y-1.5 text-[10px]">
                <div>
                  <div class="flex justify-between text-zinc-500 mb-0.5">
                    <span>X Pos</span>
                    <span class="font-mono font-bold text-zinc-800">{{ leftPct }}%</span>
                  </div>
                  <input v-model.number="leftPct" type="range" min="0" :max="Math.max(0, 100 - widthPct)" class="w-full accent-indigo-600 cursor-pointer h-1 bg-zinc-200 rounded-lg" />
                </div>

                <div>
                  <div class="flex justify-between text-zinc-500 mb-0.5">
                    <span>Y Pos</span>
                    <span class="font-mono font-bold text-zinc-800">{{ topPct }}%</span>
                  </div>
                  <input v-model.number="topPct" type="range" min="0" :max="Math.max(0, 100 - heightPct)" class="w-full accent-indigo-600 cursor-pointer h-1 bg-zinc-200 rounded-lg" />
                </div>

                <div>
                  <div class="flex justify-between text-zinc-500 mb-0.5">
                    <span>Width</span>
                    <span class="font-mono font-bold text-zinc-800">{{ widthPct }}%</span>
                  </div>
                  <input v-model.number="widthPct" type="range" min="10" :max="100 - leftPct" class="w-full accent-indigo-600 cursor-pointer h-1 bg-zinc-200 rounded-lg" />
                </div>

                <div>
                  <div class="flex justify-between text-zinc-500 mb-0.5">
                    <span>Height</span>
                    <span class="font-mono font-bold text-zinc-800">{{ heightPct }}%</span>
                  </div>
                  <input v-model.number="heightPct" type="range" min="10" :max="100 - topPct" class="w-full accent-indigo-600 cursor-pointer h-1 bg-zinc-200 rounded-lg" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-3 border-t border-zinc-100 bg-zinc-50/70 flex items-center justify-between gap-3">
        <span class="text-[11px] text-zinc-500 truncate">
          {{ activeTemplateImageUrl ? 'Ready to composite high-res mockup' : 'Please upload or select a template photo' }}
        </span>

        <div class="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" :disabled="isCompositing" @click="emit('update:open', false)">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer text-xs"
            :disabled="isCompositing || !activeTemplateImageUrl"
            @click="handleComposite"
          >
            <Icon v-if="isCompositing" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
            <span>{{ isCompositing ? 'Compositing Mockup...' : `Generate ${getMockupDisplayName(productType)} Mockup` }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
