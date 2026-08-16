<script setup lang="ts">
/* global $fetch, useRuntimeConfig */
import { ref, computed, onMounted, nextTick } from "vue";
import NavBar from "~/components/NavBar.vue";
import Button from "~/components/ui/Button.vue";
import Card from "~/components/ui/Card.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import {
  STANDARD_PRODUCT_TYPES,
  getProductLabel,
  getProductIconName,
  normalizeProductKey,
  type ProductTypeOption,
} from "~/config/productTypes";

interface PlacementData {
  left_pct: number;
  top_pct: number;
  width_pct: number;
  height_pct: number;
  angle_deg: number;
  blend_mode: string;
}

interface MockupTemplate {
  id: string;
  name: string;
  product_type: string;
  url: string;
  placement: PlacementData;
  created_at: string;
  is_custom: boolean;
}

const config = useRuntimeConfig();
const apiBase = config.public.apiBase || "http://localhost:8800";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

const templates = ref<MockupTemplate[]>([]);
const isLoading = ref(true);
const pageError = ref<string | null>(null);
const selectedCategory = ref<string>("all");
const searchQuery = ref<string>("");

// Custom products registered by user
const customProductTypes = ref<ProductTypeOption[]>([]);

// Dynamic list of all categories in tabs
const allCategoryOptions = computed(() => {
  const customMap = new Map<string, ProductTypeOption>();
  for (const t of templates.value) {
    const norm = normalizeProductKey(t.product_type);
    const isStd = STANDARD_PRODUCT_TYPES.some((s) => s.value === norm);
    if (!isStd && !customMap.has(norm)) {
      customMap.set(norm, {
        value: norm,
        label: t.product_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        icon: "lucide:package",
        isCustom: true,
      });
    }
  }
  return [...STANDARD_PRODUCT_TYPES, ...Array.from(customMap.values()), ...customProductTypes.value];
});

async function loadTemplates(): Promise<void> {
  isLoading.value = true;
  pageError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    const data = await $fetch<MockupTemplate[]>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates`,
      { headers, credentials: "include" }
    );
    templates.value = data || [];
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    pageError.value = errorObj.data?.detail || errorObj.message || "Failed to load mockup templates.";
  } finally {
    isLoading.value = false;
  }
}

const filteredTemplates = computed(() => {
  let list = templates.value;
  if (selectedCategory.value !== "all") {
    list = list.filter((t) => normalizeProductKey(t.product_type) === normalizeProductKey(selectedCategory.value));
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim();
    list = list.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.product_type.toLowerCase().includes(q)
    );
  }
  return list;
});

// Category counts map
const templateCounts = computed<Record<string, number>>(() => {
  const counts: Record<string, number> = { all: templates.value.length };
  for (const t of templates.value) {
    const k = normalizeProductKey(t.product_type);
    counts[k] = (counts[k] || 0) + 1;
  }
  return counts;
});

// Modal: Delete Template
const templateToDelete = ref<MockupTemplate | null>(null);
const isDeleting = ref(false);
const deleteError = ref<string | null>(null);

async function confirmDeleteTemplate(): Promise<void> {
  if (!templateToDelete.value) return;
  isDeleting.value = true;
  deleteError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates/${templateToDelete.value.id}`,
      {
        method: "DELETE",
        headers,
        credentials: "include",
      }
    );

    templates.value = templates.value.filter((t) => t.id !== templateToDelete.value?.id);
    templateToDelete.value = null;
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    deleteError.value = errorObj.data?.detail || errorObj.message || "Failed to delete template.";
  } finally {
    isDeleting.value = false;
  }
}

// -------------------------------------------------------------
// Interactive Placement Canvas Dragging & Resizing Logic
// -------------------------------------------------------------
const interactiveCanvasRef = ref<HTMLDivElement | null>(null);
const isDraggingArtwork = ref(false);
const isResizingArtwork = ref(false);
let dragStartX = 0;
let dragStartY = 0;
let initialLeftPct = 0;
let initialTopPct = 0;
let initialWidthPct = 0;
let initialHeightPct = 0;

// Modal: Edit Template (Name & Placement Studio)
const templateToEdit = ref<MockupTemplate | null>(null);
const editName = ref("");
const editProductType = ref("");
const editPlacement = ref<PlacementData>({
  left_pct: 0.25,
  top_pct: 0.25,
  width_pct: 0.5,
  height_pct: 0.5,
  angle_deg: 0,
  blend_mode: "multiply",
});
const isUpdating = ref(false);
const updateError = ref<string | null>(null);

function openEditModal(t: MockupTemplate): void {
  templateToEdit.value = t;
  editName.value = t.name;
  editProductType.value = t.product_type;
  editPlacement.value = {
    left_pct: t.placement.left_pct <= 1.0 ? t.placement.left_pct : t.placement.left_pct / 100,
    top_pct: t.placement.top_pct <= 1.0 ? t.placement.top_pct : t.placement.top_pct / 100,
    width_pct: t.placement.width_pct <= 1.0 ? t.placement.width_pct : t.placement.width_pct / 100,
    height_pct: t.placement.height_pct <= 1.0 ? t.placement.height_pct : t.placement.height_pct / 100,
    angle_deg: t.placement.angle_deg || 0,
    blend_mode: t.placement.blend_mode || "multiply",
  };
  updateError.value = null;
}

// Preset Placement Actions for Edit Modal
function centerEditPlacement(): void {
  const w = editPlacement.value.width_pct;
  const h = editPlacement.value.height_pct;
  editPlacement.value.left_pct = Math.max(0, Math.round(((1.0 - w) / 2) * 100) / 100);
  editPlacement.value.top_pct = Math.max(0, Math.round(((1.0 - h) / 2) * 100) / 100);
}

function applyEditChestPreset(): void {
  editPlacement.value.left_pct = 0.50;
  editPlacement.value.top_pct = 0.26;
  editPlacement.value.width_pct = 0.22;
  editPlacement.value.height_pct = 0.24;
}

function applyEditFullCenterPreset(): void {
  editPlacement.value.left_pct = 0.28;
  editPlacement.value.top_pct = 0.25;
  editPlacement.value.width_pct = 0.44;
  editPlacement.value.height_pct = 0.48;
}

function applyEditSquarePreset(): void {
  editPlacement.value.left_pct = 0.30;
  editPlacement.value.top_pct = 0.30;
  editPlacement.value.width_pct = 0.40;
  editPlacement.value.height_pct = 0.40;
}

// Pointer events for Canvas Dragging & Resizing (Edit Mode)
function onArtworkPointerDown(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isDraggingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialLeftPct = editPlacement.value.left_pct;
  initialTopPct = editPlacement.value.top_pct;

  window.addEventListener("pointermove", onArtworkPointerMove);
  window.addEventListener("pointerup", onArtworkPointerUp);
}

function onArtworkPointerMove(e: PointerEvent): void {
  if (!isDraggingArtwork.value || !interactiveCanvasRef.value) return;
  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  const dxPct = (e.clientX - dragStartX) / rect.width;
  const dyPct = (e.clientY - dragStartY) / rect.height;

  let newLeft = initialLeftPct + dxPct;
  let newTop = initialTopPct + dyPct;

  const maxL = 1.0 - editPlacement.value.width_pct;
  const maxT = 1.0 - editPlacement.value.height_pct;

  newLeft = Math.max(0, Math.min(newLeft, maxL));
  newTop = Math.max(0, Math.min(newTop, maxT));

  editPlacement.value.left_pct = Math.round(newLeft * 100) / 100;
  editPlacement.value.top_pct = Math.round(newTop * 100) / 100;
}

function onArtworkPointerUp(): void {
  isDraggingArtwork.value = false;
  window.removeEventListener("pointermove", onArtworkPointerMove);
  window.removeEventListener("pointerup", onArtworkPointerUp);
}

function onResizePointerDown(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isResizingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialWidthPct = editPlacement.value.width_pct;
  initialHeightPct = editPlacement.value.height_pct;

  window.addEventListener("pointermove", onResizePointerMove);
  window.addEventListener("pointerup", onResizePointerUp);
}

function onResizePointerMove(e: PointerEvent): void {
  if (!isResizingArtwork.value || !interactiveCanvasRef.value) return;
  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  const dxPct = (e.clientX - dragStartX) / rect.width;
  const dyPct = (e.clientY - dragStartY) / rect.height;

  let newW = initialWidthPct + dxPct;
  let newH = initialHeightPct + dyPct;

  newW = Math.max(0.1, Math.min(newW, 1.0 - editPlacement.value.left_pct));
  newH = Math.max(0.1, Math.min(newH, 1.0 - editPlacement.value.top_pct));

  editPlacement.value.width_pct = Math.round(newW * 100) / 100;
  editPlacement.value.height_pct = Math.round(newH * 100) / 100;
}

function onResizePointerUp(): void {
  isResizingArtwork.value = false;
  window.removeEventListener("pointermove", onResizePointerMove);
  window.removeEventListener("pointerup", onResizePointerUp);
}

async function handleSaveEdit(): Promise<void> {
  if (!templateToEdit.value) return;
  isUpdating.value = true;
  updateError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;

    const updated = await $fetch<MockupTemplate>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates/${templateToEdit.value.id}`,
      {
        method: "PATCH",
        headers,
        body: {
          name: editName.value.trim() || templateToEdit.value.name,
          product_type: editProductType.value,
          placement: editPlacement.value,
        },
        credentials: "include",
      }
    );

    const idx = templates.value.findIndex((t) => t.id === templateToEdit.value?.id);
    if (idx !== -1 && updated) {
      templates.value[idx] = updated;
    }
    templateToEdit.value = null;
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    updateError.value = errorObj.data?.detail || errorObj.message || "Failed to update template.";
  } finally {
    isUpdating.value = false;
  }
}

// -------------------------------------------------------------
// Upload Modal with Interactive Placement Canvas
// -------------------------------------------------------------
const showUploadModal = ref(false);
const uploadStep = ref<"file" | "placement">("file");
const uploadName = ref("");
const uploadProductType = ref("mug");
const uploadCustomTypeName = ref("");
const uploadImageFile = ref<File | null>(null);
const uploadImagePreviewUrl = ref<string | null>(null);
const uploadCanvasRef = ref<HTMLDivElement | null>(null);
const uploadPlacement = ref<PlacementData>({
  left_pct: 0.28,
  top_pct: 0.25,
  width_pct: 0.44,
  height_pct: 0.48,
  angle_deg: 0,
  blend_mode: "multiply",
});
const isUploading = ref(false);
const uploadError = ref<string | null>(null);

function handleFileSelect(e: Event): void {
  const input = e.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  uploadImageFile.value = file;
  uploadImagePreviewUrl.value = URL.createObjectURL(file);
  if (!uploadName.value) {
    uploadName.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
  }
  uploadStep.value = "placement";
}

function centerUploadPlacement(): void {
  const w = uploadPlacement.value.width_pct;
  const h = uploadPlacement.value.height_pct;
  uploadPlacement.value.left_pct = Math.max(0, Math.round(((1.0 - w) / 2) * 100) / 100);
  uploadPlacement.value.top_pct = Math.max(0, Math.round(((1.0 - h) / 2) * 100) / 100);
}

function onUploadArtworkPointerDown(e: PointerEvent): void {
  if (!uploadCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isDraggingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialLeftPct = uploadPlacement.value.left_pct;
  initialTopPct = uploadPlacement.value.top_pct;

  window.addEventListener("pointermove", onUploadArtworkPointerMove);
  window.addEventListener("pointerup", onUploadArtworkPointerUp);
}

function onUploadArtworkPointerMove(e: PointerEvent): void {
  if (!isDraggingArtwork.value || !uploadCanvasRef.value) return;
  const rect = uploadCanvasRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  const dxPct = (e.clientX - dragStartX) / rect.width;
  const dyPct = (e.clientY - dragStartY) / rect.height;

  let newLeft = initialLeftPct + dxPct;
  let newTop = initialTopPct + dyPct;

  const maxL = 1.0 - uploadPlacement.value.width_pct;
  const maxT = 1.0 - uploadPlacement.value.height_pct;

  newLeft = Math.max(0, Math.min(newLeft, maxL));
  newTop = Math.max(0, Math.min(newTop, maxT));

  uploadPlacement.value.left_pct = Math.round(newLeft * 100) / 100;
  uploadPlacement.value.top_pct = Math.round(newTop * 100) / 100;
}

function onUploadArtworkPointerUp(): void {
  isDraggingArtwork.value = false;
  window.removeEventListener("pointermove", onUploadArtworkPointerMove);
  window.removeEventListener("pointerup", onUploadArtworkPointerUp);
}

function onUploadResizePointerDown(e: PointerEvent): void {
  if (!uploadCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isResizingArtwork.value = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialWidthPct = uploadPlacement.value.width_pct;
  initialHeightPct = uploadPlacement.value.height_pct;

  window.addEventListener("pointermove", onUploadResizePointerMove);
  window.addEventListener("pointerup", onUploadResizePointerUp);
}

function onUploadResizePointerMove(e: PointerEvent): void {
  if (!isResizingArtwork.value || !uploadCanvasRef.value) return;
  const rect = uploadCanvasRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  const dxPct = (e.clientX - dragStartX) / rect.width;
  const dyPct = (e.clientY - dragStartY) / rect.height;

  let newW = initialWidthPct + dxPct;
  let newH = initialHeightPct + dyPct;

  newW = Math.max(0.1, Math.min(newW, 1.0 - uploadPlacement.value.left_pct));
  newH = Math.max(0.1, Math.min(newH, 1.0 - uploadPlacement.value.top_pct));

  uploadPlacement.value.width_pct = Math.round(newW * 100) / 100;
  uploadPlacement.value.height_pct = Math.round(newH * 100) / 100;
}

function onUploadResizePointerUp(): void {
  isResizingArtwork.value = false;
  window.removeEventListener("pointermove", onUploadResizePointerMove);
  window.removeEventListener("pointerup", onUploadResizePointerUp);
}

async function handleUploadSubmit(): Promise<void> {
  if (!uploadImageFile.value) {
    uploadError.value = "Please select an image file.";
    return;
  }
  isUploading.value = true;
  uploadError.value = null;
  try {
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const res = reader.result as string;
        const b64 = res.split(",")[1];
        resolve(b64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(uploadImageFile.value!);
    });

    const finalProductType =
      uploadProductType.value === "custom"
        ? uploadCustomTypeName.value.trim().toLowerCase().replace(/\s+/g, "_") || "custom_product"
        : uploadProductType.value;

    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;

    const created = await $fetch<MockupTemplate>(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates/upload`,
      {
        method: "POST",
        headers,
        body: {
          name: uploadName.value.trim() || "Custom Mockup",
          product_type: finalProductType,
          image_base64: base64,
          content_type: uploadImageFile.value.type || "image/jpeg",
          placement: uploadPlacement.value,
        },
        credentials: "include",
      }
    );

    if (created) {
      templates.value.unshift(created);
    }

    showUploadModal.value = false;
    uploadStep.value = "file";
    uploadImageFile.value = null;
    uploadImagePreviewUrl.value = null;
    uploadName.value = "";
    uploadCustomTypeName.value = "";
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    uploadError.value = errorObj.data?.detail || errorObj.message || "Failed to upload template.";
  } finally {
    isUploading.value = false;
  }
}

// Modal: Add Custom Product Type
const showAddCustomTypeModal = ref(false);
const newCustomTypeName = ref("");

function handleAddCustomProductType(): void {
  const name = newCustomTypeName.value.trim();
  if (!name) return;
  const key = normalizeProductKey(name);
  if (!customProductTypes.value.some((c) => c.value === key)) {
    customProductTypes.value.push({
      value: key,
      label: name,
      icon: "lucide:package",
      isCustom: true,
    });
  }
  selectedCategory.value = key;
  newCustomTypeName.value = "";
  showAddCustomTypeModal.value = false;
}

onMounted(() => {
  loadTemplates();
});
</script>

<template>
  <div class="min-h-screen bg-zinc-50/80 pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Studio Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-zinc-200/80 pb-6">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600">
            <Icon name="lucide:images" class="size-4" aria-hidden="true" />
            <span>Mockup Template Studio</span>
          </div>
          <h1 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
            Mockup Template Library
          </h1>
          <p class="text-sm text-zinc-500 max-w-2xl">
            Visually place and center artwork print areas on your blank mockup templates. Unwanted photos can be deleted here to permanently free storage.
          </p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            class="text-xs font-semibold gap-1.5 cursor-pointer text-zinc-700 hover:text-zinc-900 shadow-2xs"
            @click="showAddCustomTypeModal = true"
          >
            <Icon name="lucide:plus-circle" class="size-3.5 text-indigo-600" aria-hidden="true" />
            <span>Add Custom Product Type</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            class="text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
            @click="showUploadModal = true; uploadStep = 'file'"
          >
            <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
            <span>Upload Mockup Template</span>
          </Button>
        </div>
      </div>

      <!-- Storage Metrics & Categories Bar -->
      <div class="space-y-4">
        <!-- Search and Filter Bar -->
        <div class="flex flex-col sm:flex-row items-center justify-between gap-3">
          <!-- Search Input -->
          <div class="relative w-full sm:w-72">
            <Icon name="lucide:search" class="size-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <Input
              v-model="searchQuery"
              placeholder="Search templates..."
              class="pl-9 h-9 text-xs bg-white shadow-2xs border-zinc-200 w-full"
            />
          </div>

          <!-- Total Count Badge -->
          <div class="flex items-center gap-2 text-xs text-zinc-500">
            <span class="font-bold text-zinc-900">{{ templates.length }}</span> saved {{ templates.length === 1 ? 'template' : 'templates' }} in MinIO storage
          </div>
        </div>

        <!-- Product Category Tabs -->
        <div class="flex flex-wrap items-center gap-1.5 pt-1">
          <button
            type="button"
            class="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5"
            :class="
              selectedCategory === 'all'
                ? 'bg-zinc-900 text-white shadow-xs'
                : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200'
            "
            @click="selectedCategory = 'all'"
          >
            <Icon name="lucide:layout-grid" class="size-3.5 shrink-0" aria-hidden="true" />
            <span>All Templates</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
              :class="selectedCategory === 'all' ? 'bg-zinc-700 text-zinc-100' : 'bg-zinc-200 text-zinc-600'"
            >
              {{ templateCounts['all'] || 0 }}
            </span>
          </button>

          <button
            v-for="cat in allCategoryOptions"
            :key="cat.value"
            type="button"
            class="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5"
            :class="
              selectedCategory === cat.value
                ? 'bg-zinc-900 text-white shadow-xs'
                : 'text-zinc-600 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200'
            "
            @click="selectedCategory = cat.value"
          >
            <Icon :name="cat.icon" class="size-3.5 shrink-0" aria-hidden="true" />
            <span>{{ cat.label }}</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
              :class="
                selectedCategory === cat.value
                  ? 'bg-zinc-700 text-zinc-100'
                  : (templateCounts[cat.value] || 0) > 0
                    ? 'bg-indigo-100 text-indigo-700 font-extrabold'
                    : 'bg-zinc-200 text-zinc-500'
              "
            >
              {{ templateCounts[cat.value] || 0 }}
            </span>
          </button>
        </div>
      </div>

      <!-- Alert / Errors -->
      <Alert v-if="pageError" variant="destructive">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertDescription>{{ pageError }}</AlertDescription>
      </Alert>

      <!-- Loading State -->
      <div v-if="isLoading" class="py-20 text-center space-y-3">
        <Icon name="lucide:loader-circle" class="size-8 animate-spin mx-auto text-indigo-600" aria-hidden="true" />
        <p class="text-xs text-zinc-500">Loading mockup templates from storage...</p>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="filteredTemplates.length === 0"
        class="rounded-2xl border-2 border-dashed border-zinc-200 bg-white p-12 text-center space-y-4"
      >
        <div class="h-12 w-12 rounded-2xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center mx-auto">
          <Icon name="lucide:image-plus" class="size-6" aria-hidden="true" />
        </div>
        <div class="space-y-1 max-w-sm mx-auto">
          <h3 class="text-base font-bold text-zinc-900">
            No templates found in {{ selectedCategory === 'all' ? 'library' : getProductLabel(selectedCategory) }}
          </h3>
          <p class="text-xs text-zinc-500 leading-relaxed">
            Upload your blank product photos (e.g. flatlays, models, styled scenes) to set their print placement and use them automatically in Etsy workflows.
          </p>
        </div>
        <Button
          variant="default"
          size="sm"
          class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
          @click="showUploadModal = true; uploadStep = 'file'"
        >
          <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
          <span>Upload First Template</span>
        </Button>
      </div>

      <!-- Templates Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        <Card
          v-for="tpl in filteredTemplates"
          :key="tpl.id"
          class="overflow-hidden bg-white border border-zinc-200 shadow-2xs hover:shadow-md transition-all flex flex-col group"
        >
          <!-- Thumbnail Area with Hover Placement Overlay -->
          <div class="aspect-square bg-zinc-50 overflow-hidden relative flex items-center justify-center p-2.5 border-b border-zinc-100">
            <img
              :src="tpl.url"
              :alt="tpl.name"
              class="object-contain w-full h-full rounded-lg transition-transform duration-200 group-hover:scale-105"
            >

            <!-- Product Type Badge -->
            <Badge
              variant="outline"
              class="absolute top-2.5 left-2.5 bg-white/90 backdrop-blur-xs text-[10px] font-bold shadow-2xs gap-1 inline-flex items-center border-zinc-200"
            >
              <Icon :name="getProductIconName(tpl.product_type)" class="size-3 text-indigo-600" aria-hidden="true" />
              <span>{{ getProductLabel(tpl.product_type) }}</span>
            </Badge>

            <!-- Bounding Box Indicator Overlay on Hover -->
            <div
              class="absolute border-2 border-dashed border-indigo-600 bg-indigo-500/20 backdrop-blur-[0.5px] pointer-events-none rounded-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
              :style="{
                left: `${(tpl.placement?.left_pct ?? 0.25) * 100}%`,
                top: `${(tpl.placement?.top_pct ?? 0.25) * 100}%`,
                width: `${(tpl.placement?.width_pct ?? 0.5) * 100}%`,
                height: `${(tpl.placement?.height_pct ?? 0.5) * 100}%`,
                transform: `rotate(${tpl.placement?.angle_deg ?? 0}deg)`,
              }"
            >
              <div class="h-6 w-6 rounded-md bg-white/90 backdrop-blur-xs text-indigo-600 flex items-center justify-center shadow-xs">
                <Icon name="lucide:sparkles" class="size-3.5 text-indigo-600" aria-hidden="true" />
              </div>
            </div>
          </div>

          <!-- Card Body -->
          <div class="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
            <div class="space-y-1">
              <h4 class="text-xs font-bold text-zinc-900 truncate" :title="tpl.name">
                {{ tpl.name }}
              </h4>
              <div class="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                <span>Box: {{ Math.round((tpl.placement?.width_pct ?? 0.5) * 100) }}% × {{ Math.round((tpl.placement?.height_pct ?? 0.5) * 100) }}%</span>
                <span>•</span>
                <span class="capitalize">{{ tpl.placement?.blend_mode || 'multiply' }}</span>
              </div>
            </div>

            <!-- Action Buttons Row -->
            <div class="pt-2 border-t border-zinc-100 flex items-center justify-between gap-1.5">
              <Button
                variant="outline"
                size="sm"
                class="text-[11px] h-7 px-2 font-semibold text-zinc-700 hover:text-zinc-900 gap-1 cursor-pointer flex-1 justify-center"
                @click="openEditModal(tpl)"
              >
                <Icon name="lucide:sliders" class="size-3 text-indigo-600" aria-hidden="true" />
                <span>Adjust Placement</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                class="text-[11px] h-7 px-2 font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 gap-1 cursor-pointer"
                title="Delete template and permanently purge photo from MinIO"
                @click="templateToDelete = tpl"
              >
                <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                <span>Delete</span>
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </main>

    <!-- Modal: Delete Confirmation -->
    <div
      v-if="templateToDelete"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      @click.self="templateToDelete = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-md w-full p-6 space-y-4">
        <div class="flex items-center gap-3 text-rose-600">
          <div class="h-10 w-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center shrink-0">
            <Icon name="lucide:trash-2" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-zinc-900">Delete Mockup Template?</h3>
            <p class="text-xs text-zinc-500">Permanently delete this photo from MinIO storage.</p>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-zinc-50 border border-zinc-200/80 flex items-center gap-3">
          <img :src="templateToDelete.url" alt="Thumbnail" class="h-12 w-12 object-cover rounded-lg border border-zinc-200 shrink-0" />
          <div class="truncate">
            <p class="text-xs font-bold text-zinc-900 truncate">{{ templateToDelete.name }}</p>
            <p class="text-[10px] text-zinc-500">{{ getProductLabel(templateToDelete.product_type) }}</p>
          </div>
        </div>

        <Alert v-if="deleteError" variant="destructive">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ deleteError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" :disabled="isDeleting" @click="templateToDelete = null">
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            class="text-xs font-bold gap-1 cursor-pointer"
            :disabled="isDeleting"
            @click="confirmDeleteTemplate"
          >
            <Icon v-if="isDeleting" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
            <span>{{ isDeleting ? 'Deleting...' : 'Delete Permanently' }}</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Modal: Interactive Placement Adjustment Studio (Edit Template) -->
    <div
      v-if="templateToEdit"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      @click.self="templateToEdit = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-4xl w-full p-6 space-y-4 max-h-[92vh] flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div class="flex items-center gap-2">
            <Icon name="lucide:move" class="size-4 text-indigo-600" aria-hidden="true" />
            <div>
              <h3 class="text-sm font-bold text-zinc-900">Configure PNG Placement & Print Area</h3>
              <p class="text-[11px] text-zinc-500">Drag or resize the print box to set where master PNGs will be centered on this mockup</p>
            </div>
          </div>
          <button type="button" class="text-zinc-400 hover:text-zinc-600 cursor-pointer" @click="templateToEdit = null">
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <!-- 2-Column Split: Interactive Canvas (Left) + Placement Controls (Right) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 overflow-y-auto flex-1 p-1 items-start">
          <!-- Left Column (7 cols): Interactive Visual Canvas -->
          <div class="lg:col-span-7 space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                <Icon name="lucide:layout" class="size-3.5 text-indigo-600" aria-hidden="true" />
                <span>Interactive Placement Canvas</span>
              </span>

              <!-- Quick Placement Helpers -->
              <div class="flex items-center gap-1">
                <button
                  type="button"
                  class="px-2 py-0.5 text-[10px] font-bold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded transition-colors cursor-pointer border border-indigo-200 flex items-center gap-1"
                  @click="centerEditPlacement"
                >
                  <Icon name="lucide:align-center" class="size-3" aria-hidden="true" />
                  <span>Center Box</span>
                </button>
                <button
                  type="button"
                  class="px-2 py-0.5 text-[10px] font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded transition-colors cursor-pointer"
                  @click="applyEditFullCenterPreset"
                >
                  Full Center
                </button>
                <button
                  type="button"
                  class="px-2 py-0.5 text-[10px] font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded transition-colors cursor-pointer"
                  @click="applyEditChestPreset"
                >
                  Chest Logo
                </button>
              </div>
            </div>

            <!-- Canvas Viewport Frame -->
            <div class="relative w-full max-h-[360px] bg-zinc-950/5 rounded-xl border border-zinc-200 overflow-hidden flex items-center justify-center p-2 shadow-inner min-h-[240px]">
              <!-- Exact Image-Fitting Interactive Canvas -->
              <div
                ref="interactiveCanvasRef"
                class="relative inline-block select-none touch-none max-h-[340px] max-w-full"
              >
                <!-- Template Background Image -->
                <img
                  :src="templateToEdit.url"
                  alt="Template"
                  class="max-h-[340px] max-w-full w-auto h-auto block rounded-lg pointer-events-none object-contain shadow-xs"
                />

                <!-- Alignment Crosshairs -->
                <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-indigo-400/30 pointer-events-none" />
                <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-indigo-400/30 pointer-events-none" />

                <!-- Draggable & Resizable Placement Box -->
                <div
                  class="absolute border-2 border-indigo-600 bg-indigo-500/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-xs transition-shadow shadow-md hover:ring-2 hover:ring-indigo-400/50"
                  :style="{
                    left: `${editPlacement.left_pct * 100}%`,
                    top: `${editPlacement.top_pct * 100}%`,
                    width: `${editPlacement.width_pct * 100}%`,
                    height: `${editPlacement.height_pct * 100}%`,
                  }"
                  @pointerdown="onArtworkPointerDown"
                >
                  <!-- Live Coordinates Pill -->
                  <div class="absolute -top-6 left-1/2 -translate-x-1/2 px-1.5 py-0.2 bg-zinc-900/90 text-white rounded text-[8px] font-mono whitespace-nowrap pointer-events-none shadow-xs">
                    {{ Math.round(editPlacement.left_pct * 100) }}%, {{ Math.round(editPlacement.top_pct * 100) }}% ({{ Math.round(editPlacement.width_pct * 100) }}×{{ Math.round(editPlacement.height_pct * 100) }}%)
                  </div>

                  <!-- Centered Print Area Icon -->
                  <div class="w-full h-full pointer-events-none select-none flex items-center justify-center">
                    <div class="h-6 w-6 rounded-md bg-indigo-600/90 text-white flex items-center justify-center shadow-xs backdrop-blur-xs">
                      <Icon name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
                    </div>
                  </div>

                  <!-- Corner Resize Handle -->
                  <div
                    class="absolute -bottom-1.5 -right-1.5 h-4 w-4 bg-indigo-600 border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                    title="Drag to resize print area"
                    @pointerdown="onResizePointerDown"
                  >
                    <Icon name="lucide:maximize-2" class="size-2 text-white" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>

            <p class="text-[11px] text-zinc-500 text-center">
              💡 Click and drag the box to move · Drag the bottom-right corner circle to resize
            </p>
          </div>

          <!-- Right Column (5 cols): Placement Precision Controls & Metadata -->
          <div class="lg:col-span-5 space-y-4">
            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Template Title</Label>
              <Input v-model="editName" class="h-8 text-xs" />
            </div>

            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Product Category</Label>
              <select
                v-model="editProductType"
                class="flex h-8 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <option v-for="opt in allCategoryOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Texture Blend Mode</Label>
              <select
                v-model="editPlacement.blend_mode"
                class="flex h-8 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-xs shadow-2xs"
              >
                <option value="multiply">Multiply (Realistic Apparel Wrinkles & Shadows)</option>
                <option value="over">Over / Opaque (Ceramics, Posters, Stickers, Tumblers)</option>
              </select>
            </div>

            <!-- Precision Sliders -->
            <div class="p-3 bg-zinc-50 rounded-xl border border-zinc-200 space-y-3">
              <h5 class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider">Placement Sliders</h5>

              <div class="space-y-2">
                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-zinc-500">Box Width</span>
                    <span class="font-mono font-bold text-zinc-900">{{ Math.round(editPlacement.width_pct * 100) }}%</span>
                  </div>
                  <input type="range" v-model.number="editPlacement.width_pct" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-indigo-600 cursor-pointer" />
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-zinc-500">Box Height</span>
                    <span class="font-mono font-bold text-zinc-900">{{ Math.round(editPlacement.height_pct * 100) }}%</span>
                  </div>
                  <input type="range" v-model.number="editPlacement.height_pct" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-indigo-600 cursor-pointer" />
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-zinc-500">Left Position</span>
                    <span class="font-mono font-bold text-zinc-900">{{ Math.round(editPlacement.left_pct * 100) }}%</span>
                  </div>
                  <input type="range" v-model.number="editPlacement.left_pct" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-indigo-600 cursor-pointer" />
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-zinc-500">Top Position</span>
                    <span class="font-mono font-bold text-zinc-900">{{ Math.round(editPlacement.top_pct * 100) }}%</span>
                  </div>
                  <input type="range" v-model.number="editPlacement.top_pct" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-indigo-600 cursor-pointer" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <Alert v-if="updateError" variant="destructive">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ updateError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 pt-3 border-t border-zinc-100">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" :disabled="isUpdating" @click="templateToEdit = null">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white gap-1 cursor-pointer"
            :disabled="isUpdating"
            @click="handleSaveEdit"
          >
            <Icon v-if="isUpdating" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
            <span>{{ isUpdating ? 'Saving...' : 'Save & Center Placement' }}</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Modal: Upload Mockup Template with Visual Placement Canvas -->
    <div
      v-if="showUploadModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      @click.self="showUploadModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-4xl w-full p-6 space-y-4 max-h-[92vh] flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div class="flex items-center gap-2">
            <Icon name="lucide:upload" class="size-4 text-indigo-600" aria-hidden="true" />
            <h3 class="text-sm font-bold text-zinc-900">Upload Mockup Template & Set Placement</h3>
          </div>
          <button type="button" class="text-zinc-400 hover:text-zinc-600 cursor-pointer" @click="showUploadModal = false">
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Step 1: File Selection -->
        <div v-if="uploadStep === 'file'" class="space-y-4 py-4">
          <div class="space-y-2">
            <Label class="text-xs font-bold">Select Blank Mockup Image</Label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="block w-full text-xs text-zinc-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer border border-dashed border-zinc-300 rounded-xl p-4 text-center bg-zinc-50"
              @change="handleFileSelect"
            />
          </div>
        </div>

        <!-- Step 2: Visual Placement Studio -->
        <div v-else class="grid grid-cols-1 lg:grid-cols-12 gap-5 overflow-y-auto flex-1 p-1 items-start">
          <!-- Left Column (7 cols): Interactive Visual Canvas -->
          <div class="lg:col-span-7 space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                <Icon name="lucide:layout" class="size-3.5 text-indigo-600" aria-hidden="true" />
                <span>Designate PNG Print Area</span>
              </span>

              <button
                type="button"
                class="px-2 py-0.5 text-[10px] font-bold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded transition-colors cursor-pointer border border-indigo-200 flex items-center gap-1"
                @click="centerUploadPlacement"
              >
                <Icon name="lucide:align-center" class="size-3" aria-hidden="true" />
                <span>Center Box</span>
              </button>
            </div>

            <!-- Canvas Viewport Frame -->
            <div class="relative w-full max-h-[360px] bg-zinc-950/5 rounded-xl border border-zinc-200 overflow-hidden flex items-center justify-center p-2 shadow-inner min-h-[240px]">
              <!-- Exact Image-Fitting Upload Canvas -->
              <div
                v-if="uploadImagePreviewUrl"
                ref="uploadCanvasRef"
                class="relative inline-block select-none touch-none max-h-[340px] max-w-full"
              >
                <img
                  :src="uploadImagePreviewUrl"
                  alt="Upload Preview"
                  class="max-h-[340px] max-w-full w-auto h-auto block rounded-lg pointer-events-none object-contain shadow-xs"
                />

                <!-- Alignment Crosshairs -->
                <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-indigo-400/30 pointer-events-none" />
                <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-indigo-400/30 pointer-events-none" />

                <!-- Draggable & Resizable Placement Box -->
                <div
                  class="absolute border-2 border-indigo-600 bg-indigo-500/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-xs transition-shadow shadow-md hover:ring-2 hover:ring-indigo-400/50"
                  :style="{
                    left: `${uploadPlacement.left_pct * 100}%`,
                    top: `${uploadPlacement.top_pct * 100}%`,
                    width: `${uploadPlacement.width_pct * 100}%`,
                    height: `${uploadPlacement.height_pct * 100}%`,
                  }"
                  @pointerdown="onUploadArtworkPointerDown"
                >
                  <div class="absolute -top-6 left-1/2 -translate-x-1/2 px-1.5 py-0.2 bg-zinc-900/90 text-white rounded text-[8px] font-mono whitespace-nowrap pointer-events-none shadow-xs">
                    {{ Math.round(uploadPlacement.left_pct * 100) }}%, {{ Math.round(uploadPlacement.top_pct * 100) }}% ({{ Math.round(uploadPlacement.width_pct * 100) }}×{{ Math.round(uploadPlacement.height_pct * 100) }}%)
                  </div>

                  <!-- Centered Print Area Icon -->
                  <div class="w-full h-full pointer-events-none select-none flex items-center justify-center">
                    <div class="h-6 w-6 rounded-md bg-indigo-600/90 text-white flex items-center justify-center shadow-xs backdrop-blur-xs">
                      <Icon name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
                    </div>
                  </div>

                  <div
                    class="absolute -bottom-1.5 -right-1.5 h-4 w-4 bg-indigo-600 border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                    title="Drag to resize print area"
                    @pointerdown="onUploadResizePointerDown"
                  >
                    <Icon name="lucide:maximize-2" class="size-2 text-white" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>

            <p class="text-[11px] text-zinc-500 text-center">
              💡 Drag to position · Drag corner handle to resize print bounding box
            </p>
          </div>

          <!-- Right Column (5 cols): Metadata & Category -->
          <div class="lg:col-span-5 space-y-3.5">
            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Template Title</Label>
              <Input v-model="uploadName" placeholder="e.g. Vintage Mug on Marble Table" class="h-8 text-xs" />
            </div>

            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Product Category</Label>
              <select
                v-model="uploadProductType"
                class="flex h-8 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-xs shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <option v-for="opt in allCategoryOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
                <option value="custom">+ New Custom Product Category...</option>
              </select>
            </div>

            <div v-if="uploadProductType === 'custom'" class="space-y-1.5 animate-in fade-in">
              <Label class="text-xs font-bold text-indigo-700">Custom Category Name</Label>
              <Input v-model="uploadCustomTypeName" placeholder="e.g. Canvas Print, Pillow, Blanket" class="h-8 text-xs border-indigo-200" />
            </div>

            <div class="space-y-1.5">
              <Label class="text-xs font-bold">Texture Blend Mode</Label>
              <select
                v-model="uploadPlacement.blend_mode"
                class="flex h-8 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-xs shadow-2xs"
              >
                <option value="multiply">Multiply (Realistic Apparel Wrinkles & Shadows)</option>
                <option value="over">Over / Opaque (Ceramics, Posters, Stickers, Tumblers)</option>
              </select>
            </div>
          </div>
        </div>

        <Alert v-if="uploadError" variant="destructive">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ uploadError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 pt-3 border-t border-zinc-100">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" :disabled="isUploading" @click="showUploadModal = false">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white gap-1 cursor-pointer"
            :disabled="isUploading || !uploadImageFile"
            @click="handleUploadSubmit"
          >
            <Icon v-if="isUploading" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
            <span>{{ isUploading ? 'Uploading...' : 'Save Template & Placement' }}</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Modal: Add Custom Category -->
    <div
      v-if="showAddCustomTypeModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      @click.self="showAddCustomTypeModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-sm w-full p-6 space-y-4">
        <div class="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div class="flex items-center gap-2">
            <Icon name="lucide:plus-circle" class="size-4 text-indigo-600" aria-hidden="true" />
            <h3 class="text-sm font-bold text-zinc-900">Add Custom Product Category</h3>
          </div>
          <button type="button" class="text-zinc-400 hover:text-zinc-600 cursor-pointer" @click="showAddCustomTypeModal = false">
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <div class="space-y-2">
          <Label class="text-xs font-bold">Product Category Name</Label>
          <Input v-model="newCustomTypeName" placeholder="e.g. Canvas Print, Phone Grip, Pillow" class="h-9 text-xs" />
          <p class="text-[11px] text-zinc-500">This category will appear in your Mockup Library tabs and Intended Physical Products.</p>
        </div>

        <div class="flex justify-end gap-2 pt-2 border-t border-zinc-100">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" @click="showAddCustomTypeModal = false">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white gap-1 cursor-pointer"
            :disabled="!newCustomTypeName.trim()"
            @click="handleAddCustomProductType"
          >
            <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
            <span>Add Category</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
