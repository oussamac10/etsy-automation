<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import {
  Upload,
  Layers,
  Image as ImageIcon,
  Check,
  Loader2,
  Sparkles,
  Sliders,
  X,
  BookmarkPlus,
  Move,
  Maximize2,
  AlignCenter,
  RotateCcw,
} from "lucide-vue-next";
import Button from "~/components/ui/Button.vue";
import Badge from "~/components/ui/Badge.vue";

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
const templates = ref<MockupTemplateItem[]>([]);
const isFetchingTemplates = ref(false);

const selectedTemplateId = ref<string | null>(null);

// Form state for upload
const uploadedFile = ref<File | null>(null);
const uploadedPreviewUrl = ref<string | null>(null);
const templateName = ref("");
const saveToLibrary = ref(true);

// Placement parameters
const leftPct = ref(25);
const topPct = ref(25);
const widthPct = ref(50);
const heightPct = ref(50);
const blendMode = ref<"multiply" | "over">("multiply");

// Interactive Canvas Drag & Resize State
const interactiveCanvasRef = ref<HTMLElement | null>(null);
const isDragging = ref(false);
const isResizing = ref(false);

let dragStartX = 0;
let dragStartY = 0;
let initialLeft = 25;
let initialTop = 25;
let initialWidth = 50;
let initialHeight = 50;

const isCompositing = ref(false);
const compositeError = ref<string | null>(null);

function getMockupDisplayName(type: string): string {
  switch (type.toLowerCase()) {
    case "mug":
      return "☕ Ceramic Mug";
    case "tshirt":
      return "👕 T-Shirt";
    case "sweatshirt":
      return "🧥 Sweatshirt";
    case "tote_bag":
    case "tote":
      return "👜 Tote Bag";
    default:
      return type.toUpperCase();
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

async function fetchTemplates(): Promise<void> {
  isFetchingTemplates.value = true;
  try {
    const data = await $fetch<MockupTemplateItem[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates?product_type=${props.productType}`,
      { credentials: "include" }
    );
    templates.value = data;
    if (data.length > 0 && !selectedTemplateId.value && activeSubTab.value === "library") {
      selectedTemplateId.value = data[0].id;
      const first = data[0];
      leftPct.value = Math.round(first.placement.left_pct * 100);
      topPct.value = Math.round(first.placement.top_pct * 100);
      widthPct.value = Math.round(first.placement.width_pct * 100);
      heightPct.value = Math.round(first.placement.height_pct * 100);
      blendMode.value = first.placement.blend_mode === "over" ? "over" : "multiply";
    }
  } catch {
    templates.value = [];
  } finally {
    isFetchingTemplates.value = false;
  }
}

watch(
  () => [props.open, props.productType] as const,
  ([isOpen, prodType]) => {
    if (isOpen) {
      uploadedFile.value = null;
      uploadedPreviewUrl.value = null;
      selectedTemplateId.value = null;
      activeSubTab.value = "upload";
      compositeError.value = null;
      templateName.value = `Custom ${getMockupDisplayName(prodType)} Mockup`;
      leftPct.value = 25;
      topPct.value = 25;
      widthPct.value = 50;
      heightPct.value = 50;
      fetchTemplates();
    }
  }
);

function handleFileSelect(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    const f = target.files[0];
    uploadedFile.value = f;
    uploadedPreviewUrl.value = URL.createObjectURL(f);
    if (!templateName.value || templateName.value.startsWith("Custom ")) {
      templateName.value = f.name.replace(/\.[^/.]+$/, "");
    }
  }
}

function handleDrop(event: DragEvent): void {
  event.preventDefault();
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    const f = event.dataTransfer.files[0];
    uploadedFile.value = f;
    uploadedPreviewUrl.value = URL.createObjectURL(f);
    if (!templateName.value || templateName.value.startsWith("Custom ")) {
      templateName.value = f.name.replace(/\.[^/.]+$/, "");
    }
  }
}

function selectLibraryTemplate(tpl: MockupTemplateItem): void {
  selectedTemplateId.value = tpl.id;
  leftPct.value = Math.round(tpl.placement.left_pct * 100);
  topPct.value = Math.round(tpl.placement.top_pct * 100);
  widthPct.value = Math.round(tpl.placement.width_pct * 100);
  heightPct.value = Math.round(tpl.placement.height_pct * 100);
  blendMode.value = tpl.placement.blend_mode === "over" ? "over" : "multiply";
}

// ----------------- Interactive Manual Drag & Move Logic -----------------
function startDragMove(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  e.preventDefault();
  isDragging.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialLeft = leftPct.value;
  initialTop = topPct.value;

  window.addEventListener("pointermove", onPointerMoveDrag);
  window.addEventListener("pointerup", onPointerUpDrag);
  window.addEventListener("pointercancel", onPointerUpDrag);
}

function onPointerMoveDrag(e: PointerEvent): void {
  if (!isDragging.value || !interactiveCanvasRef.value) return;
  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;

  const deltaX = ((e.clientX - dragStartX) / rect.width) * 100;
  const deltaY = ((e.clientY - dragStartY) / rect.height) * 100;

  const maxLeft = Math.max(0, 100 - widthPct.value);
  const maxTop = Math.max(0, 100 - heightPct.value);

  const newLeft = Math.min(Math.max(0, initialLeft + deltaX), maxLeft);
  const newTop = Math.min(Math.max(0, initialTop + deltaY), maxTop);

  leftPct.value = Math.round(newLeft);
  topPct.value = Math.round(newTop);
}

function onPointerUpDrag(): void {
  isDragging.value = false;
  window.removeEventListener("pointermove", onPointerMoveDrag);
  window.removeEventListener("pointerup", onPointerUpDrag);
  window.removeEventListener("pointercancel", onPointerUpDrag);
}

// ----------------- Interactive Manual Resize Logic -----------------
function startDragResize(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isResizing.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialWidth = widthPct.value;
  initialHeight = heightPct.value;

  window.addEventListener("pointermove", onPointerMoveResize);
  window.addEventListener("pointerup", onPointerUpResize);
  window.addEventListener("pointercancel", onPointerUpResize);
}

function onPointerMoveResize(e: PointerEvent): void {
  if (!isResizing.value || !interactiveCanvasRef.value) return;
  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;

  const deltaX = ((e.clientX - dragStartX) / rect.width) * 100;
  const deltaY = ((e.clientY - dragStartY) / rect.height) * 100;

  const maxWidth = 100 - leftPct.value;
  const maxHeight = 100 - topPct.value;

  const newWidth = Math.min(Math.max(10, initialWidth + deltaX), maxWidth);
  const newHeight = Math.min(Math.max(10, initialHeight + deltaY), maxHeight);

  widthPct.value = Math.round(newWidth);
  heightPct.value = Math.round(newHeight);
}

function onPointerUpResize(): void {
  isResizing.value = false;
  window.removeEventListener("pointermove", onPointerMoveResize);
  window.removeEventListener("pointerup", onPointerUpResize);
  window.removeEventListener("pointercancel", onPointerUpResize);
}

// Quick Placement Presets
function centerHorizontally(): void {
  leftPct.value = Math.round((100 - widthPct.value) / 2);
}

function centerVertically(): void {
  topPct.value = Math.round((100 - heightPct.value) / 2);
}

function applyChestPreset(): void {
  widthPct.value = 38;
  heightPct.value = 38;
  leftPct.value = 31;
  topPct.value = 24;
}

function applyFullCenterPreset(): void {
  widthPct.value = 52;
  heightPct.value = 52;
  leftPct.value = 24;
  topPct.value = 24;
}

onUnmounted(() => {
  window.removeEventListener("pointermove", onPointerMoveDrag);
  window.removeEventListener("pointerup", onPointerUpDrag);
  window.removeEventListener("pointercancel", onPointerUpDrag);
  window.removeEventListener("pointermove", onPointerMoveResize);
  window.removeEventListener("pointerup", onPointerUpResize);
  window.removeEventListener("pointercancel", onPointerUpResize);
});

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64Data = result.split(",")[1] || result;
      resolve(base64Data);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleComposite(): Promise<void> {
  isCompositing.value = true;
  compositeError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    let templateBase64: string | undefined = undefined;
    if (activeSubTab.value === "upload") {
      if (!uploadedFile.value) {
        compositeError.value = "Please select a custom mockup template image to upload.";
        isCompositing.value = false;
        return;
      }
      templateBase64 = await fileToBase64(uploadedFile.value);
    } else {
      if (!selectedTemplateId.value) {
        compositeError.value = "Please select a saved template from your library.";
        isCompositing.value = false;
        return;
      }
    }

    const payload = {
      workflow_id: props.workflowId,
      product_type: props.productType,
      template_id: activeSubTab.value === "library" ? selectedTemplateId.value : undefined,
      template_image_base64: templateBase64,
      template_name: templateName.value || `Custom ${getMockupDisplayName(props.productType)} Mockup`,
      save_as_template: saveToLibrary.value,
      placement: {
        left_pct: leftPct.value / 100,
        top_pct: topPct.value / 100,
        width_pct: widthPct.value / 100,
        height_pct: heightPct.value / 100,
        angle_deg: 0,
        blend_mode: blendMode.value,
      },
    };

    const result = await $fetch<{ mockup_url: string; product_type: string; template_id?: string }>(
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
    const errObj = err as { data?: { detail?: string } };
    compositeError.value = errObj.data?.detail || "Failed to composite custom mockup.";
  } finally {
    isCompositing.value = false;
  }
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto"
  >
    <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 w-full max-w-3xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 my-6">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
        <div class="flex items-center gap-2.5">
          <div class="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <Layers class="h-5 w-5" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-base font-bold text-zinc-900">Custom Mockup Placer</h3>
              <span class="text-xs px-2 py-0.5 rounded-full font-semibold bg-indigo-100 text-indigo-800">
                {{ getMockupDisplayName(productType) }}
              </span>
            </div>
            <p class="text-xs text-zinc-500">Upload and position your master artwork directly on {{ getMockupDisplayName(productType) }}</p>
          </div>
        </div>
        <button
          type="button"
          class="h-8 w-8 rounded-lg hover:bg-zinc-200/70 text-zinc-400 hover:text-zinc-700 flex items-center justify-center transition-colors cursor-pointer"
          @click="emit('update:open', false)"
        >
          <X class="h-4 w-4" />
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
          <Upload class="h-3.5 w-3.5" />
          <span>Upload New {{ getMockupDisplayName(productType) }} Photo</span>
        </button>

        <button
          type="button"
          class="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
          :class="activeSubTab === 'library' ? 'bg-zinc-900 text-white shadow-xs' : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100'"
          @click="activeSubTab = 'library'"
        >
          <BookmarkPlus class="h-3.5 w-3.5" />
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
                <Upload class="h-6 w-6" />
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

        <!-- 3. INTERACTIVE VISUAL CANVAS & DIRECT MOVE TOOL -->
        <div v-if="activeTemplateImageUrl" class="space-y-3 border-t border-zinc-100 pt-4">
          <div class="flex items-center justify-between">
            <h4 class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
              <Move class="h-3.5 w-3.5 text-indigo-600" />
              <span>Interactive Positioning & Live Preview</span>
            </h4>
            <span class="text-[11px] text-zinc-500">
              💡 <strong>Click & drag</strong> box to move · <strong>Drag corner handle</strong> to resize
            </span>
          </div>

          <!-- Visual Canvas Container -->
          <div
            ref="interactiveCanvasRef"
            class="relative aspect-square max-h-[320px] mx-auto bg-zinc-900/5 rounded-xl border border-zinc-200 overflow-hidden select-none touch-none flex items-center justify-center shadow-inner"
          >
            <!-- Background Mockup Template Photo -->
            <img
              :src="activeTemplateImageUrl"
              alt="Mockup Template"
              class="w-full h-full object-contain pointer-events-none"
            />

            <!-- Alignment Center Lines -->
            <div
              class="absolute inset-0 pointer-events-none transition-opacity duration-150"
              :class="isDragging || isResizing ? 'opacity-100' : 'opacity-0'"
            >
              <div class="absolute top-0 bottom-0 left-1/2 w-px bg-indigo-500/40 border-l border-dashed border-indigo-400"></div>
              <div class="absolute left-0 right-0 top-1/2 h-px bg-indigo-500/40 border-t border-dashed border-indigo-400"></div>
            </div>

            <!-- Draggable & Resizable Artwork Box -->
            <div
              class="absolute border-2 border-indigo-500 bg-indigo-500/10 rounded-xs cursor-grab active:cursor-grabbing transition-shadow ring-1 ring-white/60 shadow-lg group z-10"
              :style="{
                left: `${leftPct}%`,
                top: `${topPct}%`,
                width: `${widthPct}%`,
                height: `${heightPct}%`,
              }"
              @pointerdown.stop="startDragMove"
            >
              <!-- Live Artwork Preview with Blend Mode -->
              <div
                class="w-full h-full flex items-center justify-center p-1 pointer-events-none"
                :style="{
                  mixBlendMode: blendMode === 'multiply' ? 'multiply' : 'normal',
                }"
              >
                <img
                  v-if="masterImageUrl"
                  :src="masterImageUrl"
                  alt="Master PNG Artwork"
                  class="w-full h-full object-contain filter drop-shadow-xs"
                />
                <div v-else class="text-center text-indigo-800 font-bold text-[10px] p-1 bg-white/80 rounded border border-indigo-200">
                  Print PNG
                </div>
              </div>

              <!-- Floating Coordinates Tooltip while dragging -->
              <div
                v-if="isDragging || isResizing"
                class="absolute -top-7 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-zinc-900/90 text-white rounded text-[10px] font-mono whitespace-nowrap pointer-events-none shadow-md z-20"
              >
                X: {{ leftPct }}% · Y: {{ topPct }}% · W: {{ widthPct }}%
              </div>

              <!-- Resize Handle in Bottom-Right Corner -->
              <div
                class="absolute -bottom-2 -right-2 h-5 w-5 bg-indigo-600 border-2 border-white rounded-full cursor-se-resize flex items-center justify-center text-white shadow-md z-30 hover:scale-125 transition-transform"
                title="Drag to resize print area"
                @pointerdown.stop="startDragResize"
              >
                <Maximize2 class="h-2.5 w-2.5" />
              </div>

              <!-- Top-Left Move Indicator -->
              <div
                class="absolute top-1 left-1 p-0.5 bg-indigo-600/80 text-white rounded-xs opacity-70 group-hover:opacity-100 pointer-events-none"
              >
                <Move class="h-2 w-2" />
              </div>
            </div>
          </div>

          <!-- Quick Alignment & Preset Buttons -->
          <div class="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div class="flex items-center gap-1.5 text-xs">
              <span class="text-[11px] text-zinc-500 font-semibold">Quick Align:</span>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-md font-medium flex items-center gap-1 transition-colors cursor-pointer"
                @click="centerHorizontally"
              >
                <AlignCenter class="h-3 w-3" />
                <span>Center Horizontally</span>
              </button>
              <button
                type="button"
                class="text-[11px] px-2 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-md font-medium flex items-center gap-1 transition-colors cursor-pointer"
                @click="centerVertically"
              >
                <AlignCenter class="h-3 w-3 rotate-90" />
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
              <Sliders class="h-3.5 w-3.5 text-indigo-600" />
              <span>Fine-Tuning Sliders & Fabric Blending</span>
            </h4>
            <div class="flex items-center gap-1">
              <button
                type="button"
                class="text-[10px] px-2 py-0.5 rounded font-medium transition-colors cursor-pointer"
                :class="blendMode === 'multiply' ? 'bg-indigo-100 text-indigo-700 font-bold' : 'bg-zinc-100 text-zinc-600'"
                @click="blendMode = 'multiply'"
              >
                Multiply (Light Garment)
              </button>
              <button
                type="button"
                class="text-[10px] px-2 py-0.5 rounded font-medium transition-colors cursor-pointer"
                :class="blendMode === 'over' ? 'bg-indigo-100 text-indigo-700 font-bold' : 'bg-zinc-100 text-zinc-600'"
                @click="blendMode = 'over'"
              >
                Opaque Over (Dark Garment)
              </button>
            </div>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
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
      <div class="px-6 py-4 border-t border-zinc-100 bg-zinc-50/50 flex items-center justify-end gap-3">
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
          <Loader2 v-if="isCompositing" class="h-3.5 w-3.5 animate-spin" />
          <Sparkles v-else class="h-3.5 w-3.5" />
          <span>{{ isCompositing ? 'Compositing Mockup...' : `Generate ${getMockupDisplayName(productType)} Mockup` }}</span>
        </Button>
      </div>
    </div>
  </div>
</template>
