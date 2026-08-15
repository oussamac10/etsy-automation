<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import Button from "~/components/ui/Button.vue";
import Badge from "~/components/ui/Badge.vue";
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

const props = defineProps<{
  open: boolean;
  workflowId: string;
  productType: string;
  masterImageUrl?: string | null;
}>();

const emit = defineEmits<{
  (e: "update:open", val: boolean): void;
  (e: "mockupCreated", result: { mockup_url: string; product_type: string; template_id?: string }): void;
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

// Reset state when opening or switching product
watch(
  () => [props.open, props.productType],
  ([isOpen]) => {
    if (isOpen) {
      compositeError.value = null;
      uploadedFile.value = null;
      uploadedPreviewUrl.value = null;
      selectedTemplateId.value = null;
      templateName.value = "";
      canvasViewMode.value = "edit";
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
      template_name: templateName.value || `${getMockupDisplayName(props.productType)} Custom Template`,
      save_as_template: saveToLibrary.value,
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
      product_type: string;
      template_id?: string;
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
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-900/60 backdrop-blur-xs animate-in fade-in duration-200"
  >
    <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-3xl w-full overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
        <div class="flex items-center gap-3">
          <div class="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <Icon name="lucide:layers" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-zinc-900">Custom Mockup Placer</h3>
              <span class="text-xs px-2 py-0.5 rounded-full font-semibold bg-indigo-100 text-indigo-800 inline-flex items-center gap-1">
                <Icon :name="getProductIcon(productType)" class="size-3 text-indigo-700" aria-hidden="true" />
                <span>{{ getMockupDisplayName(productType) }}</span>
              </span>
            </div>
            <p class="text-xs text-zinc-500">Upload, preview, and position your master artwork on {{ getMockupDisplayName(productType) }}</p>
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

      <!-- Tab Selectors: Library vs Upload -->
      <div class="px-6 pt-4 pb-2 border-b border-zinc-100 flex items-center gap-2">
        <button
          type="button"
          class="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
          :class="activeSubTab === 'upload' ? 'bg-zinc-900 text-white shadow-xs' : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100'"
          @click="activeSubTab = 'upload'"
        >
          <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
          <span>Upload New {{ getMockupDisplayName(productType) }} Photo</span>
        </button>

        <button
          type="button"
          class="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
          :class="activeSubTab === 'library' ? 'bg-zinc-900 text-white shadow-xs' : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100'"
          @click="activeSubTab = 'library'"
        >
          <Icon name="lucide:bookmark-plus" class="size-3.5" aria-hidden="true" />
          <span>Saved {{ getMockupDisplayName(productType) }} Library ({{ templates.length }})</span>
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-6 space-y-5 max-h-[72vh] overflow-y-auto">
        <!-- Error alert -->
        <div v-if="compositeError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 font-medium">
          {{ compositeError }}
        </div>

        <!-- 1. Upload Tab Content -->
        <div v-if="activeSubTab === 'upload'" class="space-y-4">
          <!-- Drop Area (if no image uploaded yet) -->
          <div
            v-if="!uploadedPreviewUrl"
            class="border-2 border-dashed border-zinc-200 hover:border-indigo-400 rounded-xl p-8 text-center cursor-pointer transition-colors bg-zinc-50/50"
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

            <div class="space-y-2 py-4">
              <div class="h-12 w-12 mx-auto rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-xs">
                <Icon name="lucide:upload" class="size-6" aria-hidden="true" />
              </div>
              <div class="text-xs font-semibold text-zinc-700">
                <span class="text-indigo-600 hover:underline">Click to upload {{ getMockupDisplayName(productType) }} photo</span> or drag and drop
              </div>
              <p class="text-[11px] text-zinc-400">High-res JPEG, PNG, or WebP photo (up to 35MB)</p>
            </div>
          </div>

          <!-- Template Name & Save checkbox -->
          <div v-if="uploadedPreviewUrl" class="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center bg-zinc-50/50 p-3 rounded-xl border border-zinc-100">
            <div>
              <label class="block text-xs font-semibold text-zinc-700 mb-1">Template Name</label>
              <input
                v-model="templateName"
                type="text"
                class="w-full text-xs px-3 py-1.5 rounded-lg border border-zinc-200 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                :placeholder="`e.g. Bella Canvas ${getMockupDisplayName(productType)} Flatlay`"
              >
            </div>

            <div class="flex items-center justify-between pt-4 sm:pt-0">
              <div class="flex items-center gap-2">
                <input
                  id="saveToLib"
                  v-model="saveToLibrary"
                  type="checkbox"
                  class="h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                >
                <label for="saveToLib" class="text-xs font-medium text-zinc-700 cursor-pointer">
                  Save to Library for {{ getMockupDisplayName(productType) }}
                </label>
              </div>

              <button
                type="button"
                class="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium underline cursor-pointer"
                @click="uploadedPreviewUrl = null; uploadedFile = null"
              >
                Change Photo
              </button>
            </div>
          </div>
        </div>

        <!-- 2. Library Tab Content -->
        <div v-else class="space-y-3">
          <div v-if="templates.length === 0" class="text-center py-6 text-zinc-400 text-xs bg-zinc-50 rounded-xl border border-dashed border-zinc-200">
            No saved custom templates found for {{ getMockupDisplayName(productType) }}. Switch to the Upload tab to add one!
          </div>

          <div v-else class="grid grid-cols-3 sm:grid-cols-4 gap-2.5 max-h-36 overflow-y-auto p-1">
            <div
              v-for="tpl in templates"
              :key="tpl.id"
              class="border rounded-xl p-2 cursor-pointer transition-all relative overflow-hidden"
              :class="selectedTemplateId === tpl.id ? 'border-indigo-600 ring-2 ring-indigo-500/20 bg-indigo-50/20' : 'border-zinc-200 hover:border-zinc-300 bg-white'"
              @click="selectLibraryTemplate(tpl)"
            >
              <div class="aspect-square bg-zinc-50 rounded-lg overflow-hidden border border-zinc-100 flex items-center justify-center mb-1">
                <img :src="tpl.url" :alt="tpl.name" class="object-cover w-full h-full" />
              </div>
              <p class="text-[11px] font-semibold text-zinc-900 truncate">{{ tpl.name }}</p>
            </div>
          </div>
        </div>

        <!-- 3. INTERACTIVE VISUAL CANVAS & PREVIEW SWITCHER -->
        <div v-if="activeTemplateImageUrl" class="space-y-3 border-t border-zinc-100 pt-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <h4 class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                <Icon
                  :name="canvasViewMode === 'edit' ? 'lucide:move' : 'lucide:eye'"
                  class="size-3.5"
                  :class="canvasViewMode === 'edit' ? 'text-indigo-600' : 'text-emerald-600'"
                  aria-hidden="true"
                />
                <span>{{ canvasViewMode === 'edit' ? 'Interactive Placement Canvas' : 'Realistic Mockup Preview' }}</span>
              </h4>
            </div>

            <!-- View Mode Switcher (Edit vs Realistic Preview) -->
            <div class="flex items-center gap-1 bg-zinc-100 p-0.5 rounded-lg border border-zinc-200">
              <button
                type="button"
                class="text-[11px] font-semibold px-2.5 py-1 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                :class="canvasViewMode === 'edit' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                @click="canvasViewMode = 'edit'"
              >
                <Icon name="lucide:sliders-horizontal" class="size-3" aria-hidden="true" />
                <span>Edit & Position</span>
              </button>

              <button
                type="button"
                class="text-[11px] font-semibold px-2.5 py-1 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                :class="canvasViewMode === 'preview' ? 'bg-indigo-600 text-white shadow-xs' : 'text-zinc-500 hover:text-zinc-900'"
                @click="canvasViewMode = 'preview'"
              >
                <Icon name="lucide:eye" class="size-3" aria-hidden="true" />
                <span>Full Realistic Preview</span>
              </button>
            </div>
          </div>

          <!-- Instruction hint -->
          <div class="text-[11px] text-zinc-500 flex items-center justify-between">
            <span v-if="canvasViewMode === 'edit'" class="flex items-center gap-1">
              <Icon name="lucide:lightbulb" class="size-3.5 text-amber-500" aria-hidden="true" />
              <span><strong>Click & drag</strong> box to move · <strong>Drag corner handle</strong> to resize</span>
            </span>
            <span v-else class="text-emerald-700 font-medium flex items-center gap-1">
              <Icon name="lucide:sparkles" class="size-3.5 text-emerald-600" aria-hidden="true" />
              <span>Viewing photorealistic preview with natural fabric folds and shadows</span>
            </span>

            <span class="font-mono text-[10px] text-zinc-400">
              X: {{ leftPct }}% · Y: {{ topPct }}% · W: {{ widthPct }}%
            </span>
          </div>

          <!-- Visual Canvas Container -->
          <div
            ref="interactiveCanvasRef"
            class="relative aspect-square max-h-[340px] mx-auto bg-zinc-900/5 rounded-xl border border-zinc-200 overflow-hidden select-none touch-none flex items-center justify-center shadow-inner"
          >
            <!-- Background Mockup Template Photo -->
            <img
              :src="activeTemplateImageUrl"
              alt="Mockup Template"
              class="w-full h-full object-contain pointer-events-none"
            />

            <!-- Alignment Center Lines (only in edit mode) -->
            <template v-if="canvasViewMode === 'edit'">
              <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-indigo-400/40 pointer-events-none" />
              <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-indigo-400/40 pointer-events-none" />
            </template>

            <!-- EDIT MODE: Draggable and Resizable Bounding Box -->
            <div
              v-if="canvasViewMode === 'edit'"
              class="absolute border-2 border-indigo-600 bg-indigo-500/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-sm transition-shadow shadow-md hover:ring-2 hover:ring-indigo-400/50"
              :style="{
                left: `${leftPct}%`,
                top: `${topPct}%`,
                width: `${widthPct}%`,
                height: `${heightPct}%`,
              }"
              @pointerdown="onArtworkPointerDown"
            >
              <!-- Coordinates tooltip pill -->
              <div class="absolute -top-7 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-zinc-900/90 text-white rounded-md text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-xs flex items-center gap-1">
                <Icon name="lucide:move" class="size-2.5 text-indigo-400" aria-hidden="true" />
                <span>{{ leftPct }}%, {{ topPct }}% ({{ widthPct }}×{{ heightPct }}%)</span>
              </div>

              <!-- Artwork Preview Thumbnail -->
              <img
                v-if="masterImageUrl"
                :src="masterImageUrl"
                alt="Artwork"
                class="w-full h-full object-contain pointer-events-none select-none drop-shadow-md"
                :class="blendMode === 'multiply' ? 'mix-blend-multiply' : 'mix-blend-normal'"
              />
              <div v-else class="text-center p-2 pointer-events-none">
                <Icon name="lucide:image" class="size-6 text-indigo-700 mx-auto mb-0.5" aria-hidden="true" />
                <span class="text-[10px] font-bold text-indigo-900 block leading-tight">Master Print Area</span>
              </div>

              <!-- Corner Scaling Handle (Bottom-Right) -->
              <div
                class="absolute -bottom-2 -right-2 h-4 w-4 bg-indigo-600 border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                title="Drag to resize print area"
                @pointerdown="onResizeHandlePointerDown"
              >
                <Icon name="lucide:maximize-2" class="size-2 text-white" aria-hidden="true" />
              </div>
            </div>

            <!-- PREVIEW MODE: Clean Natural Composite Rendering -->
            <div
              v-else-if="masterImageUrl"
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

          <!-- Quick Alignment & Preset Buttons (only in edit mode) -->
          <div v-if="canvasViewMode === 'edit'" class="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div class="flex items-center gap-1.5 text-xs">
              <span class="text-[11px] text-zinc-500 font-semibold">Quick Align:</span>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-md font-medium flex items-center gap-1 transition-colors cursor-pointer"
                @click="centerHorizontally"
              >
                <Icon name="lucide:align-center" class="size-3" aria-hidden="true" />
                <span>Center Horizontally</span>
              </button>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-md font-medium flex items-center gap-1 transition-colors cursor-pointer"
                @click="centerVertically"
              >
                <Icon name="lucide:align-center" class="size-3 rotate-90" aria-hidden="true" />
                <span>Center Vertically</span>
              </button>
            </div>

            <div class="flex items-center gap-1.5 text-xs">
              <span class="text-[11px] text-zinc-500 font-semibold">Presets:</span>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-md font-medium transition-colors cursor-pointer border border-indigo-200"
                @click="applyChestPreset"
              >
                Chest Logo
              </button>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-md font-medium transition-colors cursor-pointer border border-indigo-200"
                @click="applyFullCenterPreset"
              >
                Full Center
              </button>
            </div>
          </div>
        </div>

        <!-- 4. Fine-Tuning Precision Sliders & Texture Blend Mode -->
        <div class="border-t border-zinc-100 pt-4 space-y-3">
          <div class="flex items-center justify-between">
            <h4 class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
              <Icon name="lucide:sliders-horizontal" class="size-3.5 text-indigo-600" aria-hidden="true" />
              <span>Fabric Texture & Blend Mode</span>
            </h4>
            <div class="flex items-center gap-1">
              <button
                type="button"
                class="text-[10px] px-2 py-0.5 rounded font-medium transition-colors cursor-pointer"
                :class="blendMode === 'multiply' ? 'bg-indigo-100 text-indigo-700 font-bold' : 'bg-zinc-100 text-zinc-600'"
                @click="blendMode = 'multiply'"
              >
                Multiply (Light Garments)
              </button>
              <button
                type="button"
                class="text-[10px] px-2 py-0.5 rounded font-medium transition-colors cursor-pointer"
                :class="blendMode === 'over' ? 'bg-indigo-100 text-indigo-700 font-bold' : 'bg-zinc-100 text-zinc-600'"
                @click="blendMode = 'over'"
              >
                Opaque Over (Dark Garments)
              </button>
            </div>
          </div>

          <div v-if="canvasViewMode === 'edit'" class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <div class="flex justify-between text-[11px] text-zinc-500 mb-1">
                <span>Left Position (X)</span>
                <span class="font-mono font-bold">{{ leftPct }}%</span>
              </div>
              <input v-model.number="leftPct" type="range" min="0" :max="Math.max(0, 100 - widthPct)" class="w-full accent-indigo-600 cursor-pointer" />
            </div>

            <div>
              <div class="flex justify-between text-[11px] text-zinc-500 mb-1">
                <span>Top Position (Y)</span>
                <span class="font-mono font-bold">{{ topPct }}%</span>
              </div>
              <input v-model.number="topPct" type="range" min="0" :max="Math.max(0, 100 - heightPct)" class="w-full accent-indigo-600 cursor-pointer" />
            </div>

            <div>
              <div class="flex justify-between text-[11px] text-zinc-500 mb-1">
                <span>Print Width</span>
                <span class="font-mono font-bold">{{ widthPct }}%</span>
              </div>
              <input v-model.number="widthPct" type="range" min="10" :max="100 - leftPct" class="w-full accent-indigo-600 cursor-pointer" />
            </div>

            <div>
              <div class="flex justify-between text-[11px] text-zinc-500 mb-1">
                <span>Print Height</span>
                <span class="font-mono font-bold">{{ heightPct }}%</span>
              </div>
              <input v-model.number="heightPct" type="range" min="10" :max="100 - topPct" class="w-full accent-indigo-600 cursor-pointer" />
            </div>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-6 py-4 border-t border-zinc-100 bg-zinc-50/50 flex items-center justify-between gap-3">
        <button
          v-if="canvasViewMode === 'edit' && activeTemplateImageUrl"
          type="button"
          class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 cursor-pointer"
          @click="canvasViewMode = 'preview'"
        >
          <Icon name="lucide:eye" class="size-3.5" aria-hidden="true" />
          <span>Switch to Full Realistic Preview</span>
        </button>

        <button
          v-else-if="canvasViewMode === 'preview'"
          type="button"
          class="text-xs font-semibold text-zinc-600 hover:text-zinc-900 flex items-center gap-1 cursor-pointer"
          @click="canvasViewMode = 'edit'"
        >
          <Icon name="lucide:sliders-horizontal" class="size-3.5" aria-hidden="true" />
          <span>Back to Adjust Position</span>
        </button>

        <div v-else></div>

        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" :disabled="isCompositing" @click="emit('update:open', false)">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer"
            :disabled="isCompositing || (activeSubTab === 'upload' && !uploadedFile) || (activeSubTab === 'library' && !selectedTemplateId)"
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
