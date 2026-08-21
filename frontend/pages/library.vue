<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import NavBar from "~/components/NavBar.vue";
import Button from "~/components/ui/Button.vue";
import Card from "~/components/ui/Card.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Pagination from "~/components/ui/Pagination.vue";
import ImageCropperView from "~/components/ui/ImageCropperView.vue";
import {
  STANDARD_PRODUCT_TYPES,
  getProductLabel,
  getProductIconName,
  normalizeProductKey,
  type ProductTypeOption,
} from "~/config/productTypes";
import { BLEND_MODE_OPTIONS, getBlendModeInfo } from "~/utils/mockupProducts";

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
  const mergedMap = new Map<string, ProductTypeOption>();

  // 1. Standard product types
  for (const std of STANDARD_PRODUCT_TYPES) {
    mergedMap.set(std.value, std);
  }

  // 2. Custom categories from templates
  for (const t of templates.value) {
    const norm = normalizeProductKey(t.product_type);
    if (!mergedMap.has(norm)) {
      mergedMap.set(norm, {
        value: norm,
        label: t.product_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        icon: "lucide:package",
        isCustom: true,
      });
    }
  }

  // 3. Newly created custom categories that don't have templates yet
  for (const c of customProductTypes.value) {
    const norm = normalizeProductKey(c.value);
    if (!mergedMap.has(norm)) {
      mergedMap.set(norm, {
        ...c,
        value: norm,
      });
    }
  }

  return Array.from(mergedMap.values());
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

// Pagination state (Max 20 per page)
const currentPage = ref(1);
const pageSize = 20;
const totalFilteredTemplates = computed(() => filteredTemplates.value.length);
const paginatedTemplates = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredTemplates.value.slice(start, start + pageSize);
});

watch([selectedCategory, searchQuery], () => {
  currentPage.value = 1;
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

// Modal: Delete Category & all its Mockups
const showDeleteCategoryModal = ref(false);
const categoryToDelete = ref<string | null>(null);
const isDeletingCategory = ref(false);
const deleteCategoryError = ref<string | null>(null);

function promptDeleteCategory(categoryKey: string): void {
  categoryToDelete.value = categoryKey;
  deleteCategoryError.value = null;
  showDeleteCategoryModal.value = true;
}

async function confirmDeleteCategory(): Promise<void> {
  if (!categoryToDelete.value) return;
  isDeletingCategory.value = true;
  deleteCategoryError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) headers["x-csrf-token"] = csrf;

    const catKey = categoryToDelete.value;
    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates/categories/${encodeURIComponent(catKey)}`,
      {
        method: "DELETE",
        headers,
        credentials: "include",
      }
    );

    // Remove templates from local state
    templates.value = templates.value.filter(
      (t) => normalizeProductKey(t.product_type) !== normalizeProductKey(catKey)
    );
    // Remove from customProductTypes
    customProductTypes.value = customProductTypes.value.filter(
      (c) => c.value !== catKey
    );

    if (selectedCategory.value === catKey) {
      selectedCategory.value = "all";
    }
    showDeleteCategoryModal.value = false;
    categoryToDelete.value = null;
  } catch (err: unknown) {
    const errorObj = err as { data?: { detail?: string }; message?: string };
    deleteCategoryError.value = errorObj.data?.detail || errorObj.message || "Failed to delete category.";
  } finally {
    isDeletingCategory.value = false;
  }
}

// -------------------------------------------------------------
// Interactive Placement Canvas Dragging, Resizing & Rotating Logic
// -------------------------------------------------------------
const interactiveCanvasRef = ref<HTMLDivElement | null>(null);
const isDraggingArtwork = ref(false);
const isResizingArtwork = ref(false);
const isRotatingArtwork = ref(false);
let dragStartX = 0;
let dragStartY = 0;
let initialLeftPct = 0;
let initialTopPct = 0;
let initialWidthPct = 0;
let initialHeightPct = 0;
let rotateCenterScreenX = 0;
let rotateCenterScreenY = 0;
let rotateStartAngleRad = 0;
let initialAngleDeg = 0;

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

function rotateEditLeft(): void {
  let a = (editPlacement.value.angle_deg || 0) - 90;
  while (a < -180) a += 360;
  editPlacement.value.angle_deg = a;
}

function rotateEditRight(): void {
  let a = (editPlacement.value.angle_deg || 0) + 90;
  while (a > 180) a -= 360;
  editPlacement.value.angle_deg = a;
}

function setEditAngle(deg: number): void {
  editPlacement.value.angle_deg = deg;
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

function onEditRotatePointerDown(e: PointerEvent): void {
  if (!interactiveCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isRotatingArtwork.value = true;

  const rect = interactiveCanvasRef.value.getBoundingClientRect();
  const boxCenterX = rect.left + (editPlacement.value.left_pct + editPlacement.value.width_pct / 2) * rect.width;
  const boxCenterY = rect.top + (editPlacement.value.top_pct + editPlacement.value.height_pct / 2) * rect.height;

  rotateCenterScreenX = boxCenterX;
  rotateCenterScreenY = boxCenterY;
  rotateStartAngleRad = Math.atan2(e.clientY - boxCenterY, e.clientX - boxCenterX);
  initialAngleDeg = editPlacement.value.angle_deg || 0;

  window.addEventListener("pointermove", onEditRotatePointerMove);
  window.addEventListener("pointerup", onEditRotatePointerUp);
}

function onEditRotatePointerMove(e: PointerEvent): void {
  if (!isRotatingArtwork.value) return;
  const currentAngleRad = Math.atan2(e.clientY - rotateCenterScreenY, e.clientX - rotateCenterScreenX);
  const deltaDeg = (currentAngleRad - rotateStartAngleRad) * (180 / Math.PI);
  let newAngle = Math.round(initialAngleDeg + deltaDeg);
  while (newAngle > 180) newAngle -= 360;
  while (newAngle < -180) newAngle += 360;
  editPlacement.value.angle_deg = newAngle;
}

function onEditRotatePointerUp(): void {
  isRotatingArtwork.value = false;
  window.removeEventListener("pointermove", onEditRotatePointerMove);
  window.removeEventListener("pointerup", onEditRotatePointerUp);
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
const showCategoryDropdown = ref(false);
const uploadStep = ref<"file" | "crop" | "placement">("file");
const uploadName = ref("");
const uploadProductType = ref("mug");
const uploadCustomTypeName = ref("");
const uploadImageFile = ref<File | null>(null);
const uploadImagePreviewUrl = ref<string | null>(null);
const rawUploadFileUrl = ref<string | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDraggingFile = ref(false);
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

function openUploadModal(forcedCategory?: string): void {
  const targetCategory = forcedCategory || (selectedCategory.value !== "all" ? selectedCategory.value : "mug");
  uploadProductType.value = targetCategory;
  uploadCustomTypeName.value = "";
  showCategoryDropdown.value = selectedCategory.value === "all";

  const norm = normalizeProductKey(targetCategory);
  if (norm === "tshirt" || norm === "sweatshirt" || norm === "tote_bag") {
    uploadPlacement.value = {
      left_pct: 0.28,
      top_pct: 0.25,
      width_pct: 0.44,
      height_pct: 0.48,
      angle_deg: 0,
      blend_mode: "multiply",
    };
  } else if (norm === "poster") {
    uploadPlacement.value = {
      left_pct: 0.20,
      top_pct: 0.20,
      width_pct: 0.60,
      height_pct: 0.60,
      angle_deg: 0,
      blend_mode: "over",
    };
  } else {
    uploadPlacement.value = {
      left_pct: 0.28,
      top_pct: 0.25,
      width_pct: 0.44,
      height_pct: 0.48,
      angle_deg: 0,
      blend_mode: "over",
    };
  }

  uploadName.value = "";
  uploadImageFile.value = null;
  uploadImagePreviewUrl.value = null;
  rawUploadFileUrl.value = null;
  uploadStep.value = "file";
  uploadError.value = null;
  isDraggingFile.value = false;
  showUploadModal.value = true;
}

function handleFileSelect(e: Event): void {
  const input = e.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  uploadImageFile.value = file;
  rawUploadFileUrl.value = URL.createObjectURL(file);
  uploadImagePreviewUrl.value = rawUploadFileUrl.value;
  if (!uploadName.value) {
    uploadName.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
  }
  uploadStep.value = "placement";
}

function onFileDragOver(e: DragEvent): void {
  e.preventDefault();
  isDraggingFile.value = true;
}

function onFileDragLeave(e: DragEvent): void {
  e.preventDefault();
  isDraggingFile.value = false;
}

function onFileDrop(e: DragEvent): void {
  e.preventDefault();
  isDraggingFile.value = false;
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    const file = e.dataTransfer.files[0];
    if (file.type.startsWith("image/")) {
      uploadImageFile.value = file;
      rawUploadFileUrl.value = URL.createObjectURL(file);
      uploadImagePreviewUrl.value = rawUploadFileUrl.value;
      if (!uploadName.value) {
        uploadName.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
      }
      uploadStep.value = "placement";
    }
  }
}

function handleUploadCropComplete(result: {
  croppedFile: File;
  croppedUrl: string;
}): void {
  uploadImageFile.value = result.croppedFile;
  uploadImagePreviewUrl.value = result.croppedUrl;
  uploadStep.value = "placement";
}

function centerUploadPlacement(): void {
  const w = uploadPlacement.value.width_pct;
  const h = uploadPlacement.value.height_pct;
  uploadPlacement.value.left_pct = Math.max(0, Math.round(((1.0 - w) / 2) * 100) / 100);
  uploadPlacement.value.top_pct = Math.max(0, Math.round(((1.0 - h) / 2) * 100) / 100);
}

function applyUploadChestPreset(): void {
  uploadPlacement.value.left_pct = 0.50;
  uploadPlacement.value.top_pct = 0.26;
  uploadPlacement.value.width_pct = 0.22;
  uploadPlacement.value.height_pct = 0.24;
}

function applyUploadFullCenterPreset(): void {
  uploadPlacement.value.left_pct = 0.28;
  uploadPlacement.value.top_pct = 0.25;
  uploadPlacement.value.width_pct = 0.44;
  uploadPlacement.value.height_pct = 0.48;
}

function applyUploadSquarePreset(): void {
  uploadPlacement.value.left_pct = 0.30;
  uploadPlacement.value.top_pct = 0.30;
  uploadPlacement.value.width_pct = 0.40;
  uploadPlacement.value.height_pct = 0.40;
}

function rotateUploadLeft(): void {
  let a = (uploadPlacement.value.angle_deg || 0) - 90;
  while (a < -180) a += 360;
  uploadPlacement.value.angle_deg = a;
}

function rotateUploadRight(): void {
  let a = (uploadPlacement.value.angle_deg || 0) + 90;
  while (a > 180) a -= 360;
  uploadPlacement.value.angle_deg = a;
}

function setUploadAngle(deg: number): void {
  uploadPlacement.value.angle_deg = deg;
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

function onUploadRotatePointerDown(e: PointerEvent): void {
  if (!uploadCanvasRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isRotatingArtwork.value = true;

  const rect = uploadCanvasRef.value.getBoundingClientRect();
  const boxCenterX = rect.left + (uploadPlacement.value.left_pct + uploadPlacement.value.width_pct / 2) * rect.width;
  const boxCenterY = rect.top + (uploadPlacement.value.top_pct + uploadPlacement.value.height_pct / 2) * rect.height;

  rotateCenterScreenX = boxCenterX;
  rotateCenterScreenY = boxCenterY;
  rotateStartAngleRad = Math.atan2(e.clientY - boxCenterY, e.clientX - boxCenterX);
  initialAngleDeg = uploadPlacement.value.angle_deg || 0;

  window.addEventListener("pointermove", onUploadRotatePointerMove);
  window.addEventListener("pointerup", onUploadRotatePointerUp);
}

function onUploadRotatePointerMove(e: PointerEvent): void {
  if (!isRotatingArtwork.value) return;
  const currentAngleRad = Math.atan2(e.clientY - rotateCenterScreenY, e.clientX - rotateCenterScreenX);
  const deltaDeg = (currentAngleRad - rotateStartAngleRad) * (180 / Math.PI);
  let newAngle = Math.round(initialAngleDeg + deltaDeg);
  while (newAngle > 180) newAngle -= 360;
  while (newAngle < -180) newAngle += 360;
  uploadPlacement.value.angle_deg = newAngle;
}

function onUploadRotatePointerUp(): void {
  isRotatingArtwork.value = false;
  window.removeEventListener("pointermove", onUploadRotatePointerMove);
  window.removeEventListener("pointerup", onUploadRotatePointerUp);
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
  openUploadModal(key);
}

onMounted(() => {
  loadTemplates();
});
</script>

<template>
  <div class="min-h-screen bg-background pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Studio Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-border pb-6">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <Icon name="lucide:images" class="size-4" aria-hidden="true" />
            <span>Mockup Template Studio</span>
          </div>
          <h1 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
            Mockup Template Library
          </h1>
          <p class="text-sm text-muted-foreground max-w-2xl">
            Visually place and center artwork print areas on your blank mockup templates. Unwanted photos can be deleted here to permanently free storage.
          </p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            class="text-xs font-semibold gap-1.5 cursor-pointer text-secondary-foreground hover:text-foreground shadow-2xs"
            @click="showAddCustomTypeModal = true"
          >
            <Icon name="lucide:plus-circle" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Add Custom Product Type</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            class="text-xs font-semibold gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
            @click="openUploadModal()"
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
            <Icon name="lucide:search" class="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <Input
              v-model="searchQuery"
              placeholder="Search templates..."
              class="pl-9 h-9 text-xs bg-white shadow-2xs border-border w-full"
            />
          </div>

          <!-- Total Count Badge -->
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <span class="font-bold text-foreground">{{ templates.length }}</span> saved {{ templates.length === 1 ? 'template' : 'templates' }} in your library
          </div>
        </div>

        <!-- Product Category Tabs -->
        <div class="flex flex-wrap items-center gap-1.5 pt-1">
          <button
            type="button"
            class="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer inline-flex items-center gap-1.5"
            :class="
              selectedCategory === 'all'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-secondary-foreground hover:text-foreground bg-secondary hover:bg-slate-200'
            "
            @click="selectedCategory = 'all'"
          >
            <Icon name="lucide:layout-grid" class="size-3.5 shrink-0" aria-hidden="true" />
            <span>All Templates</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
              :class="selectedCategory === 'all' ? 'bg-slate-700 text-white' : 'bg-white text-secondary-foreground border border-border'"
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
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-secondary-foreground hover:text-foreground bg-secondary hover:bg-slate-200'
            "
            @click="selectedCategory = cat.value"
          >
            <Icon :name="cat.icon" class="size-3.5 shrink-0" aria-hidden="true" />
            <span>{{ cat.label }}</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full font-bold"
              :class="
                selectedCategory === cat.value
                  ? 'bg-slate-700 text-white'
                  : (templateCounts[cat.value] || 0) > 0
                    ? 'bg-blue-50 text-primary font-extrabold border border-blue-200'
                    : 'bg-white text-muted-foreground border border-border'
              "
            >
              {{ templateCounts[cat.value] || 0 }}
            </span>
          </button>
        </div>
      </div>

      <!-- Selected Category Banner / Actions -->
      <div
        v-if="selectedCategory !== 'all'"
        class="flex items-center justify-between bg-white rounded-xl p-3.5 border border-border shadow-2xs"
      >
        <div class="flex items-center gap-2.5">
          <div class="size-8 rounded-lg bg-secondary text-primary flex items-center justify-center border border-border shadow-2xs">
            <Icon :name="getProductIconName(selectedCategory)" class="size-4" aria-hidden="true" />
          </div>
          <div>
            <h4 class="text-xs font-bold text-foreground flex items-center gap-1.5">
              <span>{{ getProductLabel(selectedCategory) }}</span>
              <Badge v-if="allCategoryOptions.find(c => c.value === selectedCategory)?.isCustom" variant="outline" class="text-[9px] bg-secondary text-primary border-border">
                Custom Category
              </Badge>
            </h4>
            <p class="text-[11px] text-muted-foreground">
              {{ templateCounts[selectedCategory] || 0 }} {{ (templateCounts[selectedCategory] || 0) === 1 ? 'mockup template' : 'mockup templates' }} in this category
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            class="text-xs text-destructive hover:text-destructive hover:bg-red-50 hover:border-red-200 gap-1.5 cursor-pointer font-semibold shadow-2xs"
            @click="promptDeleteCategory(selectedCategory)"
          >
            <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
            <span>Delete Category & Mockups</span>
          </Button>
        </div>
      </div>

      <!-- Alert / Errors -->
      <Alert v-if="pageError" variant="destructive">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertDescription>{{ pageError }}</AlertDescription>
      </Alert>

      <!-- Loading State -->
      <div v-if="isLoading" class="py-20 text-center space-y-3">
        <Icon name="lucide:loader-circle" class="size-8 animate-spin mx-auto text-primary" aria-hidden="true" />
        <p class="text-xs text-muted-foreground">Loading mockup templates from storage...</p>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="filteredTemplates.length === 0"
        class="rounded-2xl border-2 border-dashed border-border bg-white p-12 text-center space-y-4"
      >
        <div class="h-12 w-12 rounded-2xl bg-secondary border border-border text-primary flex items-center justify-center mx-auto">
          <Icon name="lucide:image-plus" class="size-6" aria-hidden="true" />
        </div>
        <div class="space-y-1 max-w-sm mx-auto">
          <h3 class="text-base font-bold text-foreground">
            No templates found in {{ selectedCategory === 'all' ? 'library' : getProductLabel(selectedCategory) }}
          </h3>
          <p class="text-xs text-muted-foreground leading-relaxed">
            Upload your blank product photos (e.g. flatlays, models, styled scenes) to set their print placement and use them automatically in design workflows.
          </p>
        </div>
        <div class="flex items-center justify-center gap-2.5">
          <Button
            variant="default"
            size="sm"
            class="font-bold text-xs gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
            @click="openUploadModal()"
          >
            <Icon name="lucide:upload" class="size-3.5" aria-hidden="true" />
            <span>Upload First Template</span>
          </Button>
          <Button
            v-if="selectedCategory !== 'all'"
            variant="outline"
            size="sm"
            class="text-xs text-destructive hover:text-destructive hover:bg-red-50 hover:border-red-200 gap-1.5 cursor-pointer font-medium"
            @click="promptDeleteCategory(selectedCategory)"
          >
            <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
            <span>Delete Category</span>
          </Button>
        </div>
      </div>

      <!-- Templates Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        <Card
          v-for="tpl in paginatedTemplates"
          :key="tpl.id"
          class="overflow-hidden bg-white border border-border shadow-2xs hover:shadow-md transition-all flex flex-col group"
        >
          <!-- Thumbnail Area with Hover Placement Overlay -->
          <div class="aspect-square bg-secondary/30 overflow-hidden relative flex items-center justify-center p-2.5 border-b border-border">
            <img
              :src="tpl.url"
              :alt="tpl.name"
              class="object-contain w-full h-full rounded-lg transition-transform duration-200 group-hover:scale-105"
            >

            <!-- Product Type Badge -->
            <Badge
              variant="outline"
              class="absolute top-2.5 left-2.5 bg-white/90 backdrop-blur-xs text-[10px] font-bold shadow-2xs gap-1 inline-flex items-center border-border text-foreground"
            >
              <Icon :name="getProductIconName(tpl.product_type)" class="size-3 text-primary" aria-hidden="true" />
              <span>{{ getProductLabel(tpl.product_type) }}</span>
            </Badge>

            <!-- Bounding Box Indicator Overlay on Hover -->
            <div
              class="absolute border-2 border-dashed border-primary bg-primary/20 backdrop-blur-[0.5px] pointer-events-none rounded-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
              :style="{
                left: `${(tpl.placement?.left_pct ?? 0.25) * 100}%`,
                top: `${(tpl.placement?.top_pct ?? 0.25) * 100}%`,
                width: `${(tpl.placement?.width_pct ?? 0.5) * 100}%`,
                height: `${(tpl.placement?.height_pct ?? 0.5) * 100}%`,
                transform: `rotate(${tpl.placement?.angle_deg ?? 0}deg)`,
              }"
            >
              <div class="h-6 w-6 rounded-md bg-white/90 backdrop-blur-xs text-primary flex items-center justify-center shadow-xs">
                <Icon name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
              </div>
            </div>
          </div>

          <!-- Card Body -->
          <div class="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
            <div class="space-y-1">
              <h4 class="text-xs font-bold text-foreground truncate" :title="tpl.name">
                {{ tpl.name }}
              </h4>
              <div class="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                <span>Box: {{ Math.round((tpl.placement?.width_pct ?? 0.5) * 100) }}% × {{ Math.round((tpl.placement?.height_pct ?? 0.5) * 100) }}%</span>
                <span>•</span>
                <span class="capitalize">{{ tpl.placement?.blend_mode || 'multiply' }}</span>
              </div>
            </div>

            <!-- Action Buttons Row -->
            <div class="pt-2 border-t border-border flex items-center justify-between gap-1.5">
              <Button
                variant="outline"
                size="sm"
                class="text-[11px] h-7 px-2 font-semibold text-secondary-foreground hover:text-foreground gap-1 cursor-pointer flex-1 justify-center"
                @click="openEditModal(tpl)"
              >
                <Icon name="lucide:sliders" class="size-3 text-primary" aria-hidden="true" />
                <span>Adjust Placement</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                class="text-[11px] h-7 px-2 font-semibold text-destructive hover:text-destructive hover:bg-red-50 border-red-200 gap-1 cursor-pointer"
                title="Delete template and remove photo from your library"
                @click="templateToDelete = tpl"
              >
                <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
                <span>Delete</span>
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <!-- Pagination Bar -->
      <Pagination
        v-if="filteredTemplates.length > 0"
        v-model:current-page="currentPage"
        :total-items="totalFilteredTemplates"
        :page-size="pageSize"
        class="mt-6"
      />
    </main>

    <!-- Modal: Delete Confirmation -->
    <div
      v-if="templateToDelete"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200"
      @click.self="templateToDelete = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-border max-w-md w-full p-6 space-y-4">
        <div class="flex items-center gap-3 text-destructive">
          <div class="h-10 w-10 rounded-xl bg-red-50 border border-red-200 flex items-center justify-center shrink-0">
            <Icon name="lucide:trash-2" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-foreground">Delete Mockup Template?</h3>
            <p class="text-xs text-muted-foreground">Permanently delete this template from your library.</p>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-secondary/40 border border-border flex items-center gap-3">
          <img :src="templateToDelete.url" alt="Thumbnail" class="h-12 w-12 object-cover rounded-lg border border-border shrink-0">
          <div class="truncate">
            <p class="text-xs font-bold text-foreground truncate">{{ templateToDelete.name }}</p>
            <p class="text-[10px] text-muted-foreground">{{ getProductLabel(templateToDelete.product_type) }}</p>
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
      class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-200"
      @click.self="templateToEdit = null"
    >
      <div class="bg-card rounded-2xl shadow-2xl border border-border max-w-5xl w-full flex flex-col max-h-[92vh] overflow-hidden">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-border p-4 sm:p-5 bg-card/50">
          <div class="flex items-center gap-3">
            <div class="size-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 shadow-2xs">
              <Icon name="lucide:move" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <h3 class="text-base sm:text-lg font-bold text-foreground">Configure PNG Placement & Print Area</h3>
              <p class="text-xs text-muted-foreground">Adjust placement bounding box, rotation angle, and texture blend mode</p>
            </div>
          </div>
          <button
            type="button"
            class="size-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
            @click="templateToEdit = null"
          >
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <!-- 2-Column Split: Interactive Canvas (Left) + Placement Controls (Right) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 overflow-y-auto flex-1 p-5 items-start">
          <!-- Left Column (7 cols): Interactive Visual Canvas -->
          <div class="lg:col-span-7 space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Icon name="lucide:layout" class="size-3.5 text-primary" aria-hidden="true" />
                <span>Interactive Placement Canvas</span>
              </span>

              <!-- Quick Placement & Rotation Segmented Toolbar -->
              <div class="flex items-center gap-1.5 flex-wrap">
                <div class="flex items-center gap-1 bg-secondary/80 p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Center artwork box"
                    @click="centerEditPlacement"
                  >
                    <Icon name="lucide:align-center" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Center</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply full center preset"
                    @click="applyEditFullCenterPreset"
                  >
                    <Icon name="lucide:maximize-2" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Full</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply left chest preset"
                    @click="applyEditChestPreset"
                  >
                    <Icon name="lucide:target" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Chest</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply square 1:1 preset"
                    @click="applyEditSquarePreset"
                  >
                    <Icon name="lucide:square" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>1:1</span>
                  </button>
                </div>

                <!-- Rotation Quick Tools -->
                <div class="flex items-center gap-1 bg-secondary/80 p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Rotate 90 degrees counter-clockwise"
                    @click="rotateEditLeft"
                  >
                    <Icon name="lucide:rotate-ccw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>-90°</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Rotate 90 degrees clockwise"
                    @click="rotateEditRight"
                  >
                    <Icon name="lucide:rotate-cw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>+90°</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Reset rotation to 0°"
                    @click="setEditAngle(0)"
                  >
                    <span>0°</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Canvas Viewport Frame -->
            <div class="relative w-full max-h-[380px] bg-slate-950/90 rounded-2xl border border-slate-800 overflow-hidden flex items-center justify-center p-3 shadow-inner min-h-[260px]">
              <!-- Exact Image-Fitting Interactive Canvas -->
              <div
                ref="interactiveCanvasRef"
                class="relative inline-block select-none touch-none max-h-[350px] max-w-full"
              >
                <!-- Template Background Image -->
                <img
                  :src="templateToEdit.url"
                  alt="Template"
                  class="max-h-[350px] max-w-full w-auto h-auto block rounded-lg pointer-events-none object-contain shadow-md"
                >

                <!-- Alignment Crosshairs -->
                <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-primary/30 pointer-events-none" />
                <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-primary/30 pointer-events-none" />

                <!-- Draggable, Resizable & Rotatable Placement Box -->
                <div
                  class="absolute border-2 border-primary bg-primary/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-xs transition-shadow shadow-md hover:ring-2 hover:ring-primary/50 select-none"
                  :style="{
                    left: `${editPlacement.left_pct * 100}%`,
                    top: `${editPlacement.top_pct * 100}%`,
                    width: `${editPlacement.width_pct * 100}%`,
                    height: `${editPlacement.height_pct * 100}%`,
                    transform: `rotate(${editPlacement.angle_deg || 0}deg)`,
                    transformOrigin: 'center center',
                  }"
                  @pointerdown="onArtworkPointerDown"
                >
                  <!-- Top Rotation Stalk & Handle -->
                  <div class="absolute -top-7 left-1/2 -translate-x-1/2 flex flex-col items-center pointer-events-auto select-none">
                    <div
                      class="size-5 rounded-full bg-primary text-white border-2 border-white shadow-md flex items-center justify-center cursor-grab active:cursor-grabbing hover:scale-125 transition-transform"
                      title="Drag to rotate print area"
                      @pointerdown="onEditRotatePointerDown"
                    >
                      <Icon name="lucide:rotate-cw" class="size-2.5 text-white" aria-hidden="true" />
                    </div>
                    <div class="w-0.5 h-2 bg-primary/70" />
                  </div>

                  <!-- Live Coordinates Pill -->
                  <div class="absolute -top-12 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-slate-900/90 text-white rounded-md text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-md border border-slate-700/60">
                    {{ Math.round(editPlacement.left_pct * 100) }}%, {{ Math.round(editPlacement.top_pct * 100) }}% · {{ Math.round(editPlacement.width_pct * 100) }}×{{ Math.round(editPlacement.height_pct * 100) }}% · {{ editPlacement.angle_deg || 0 }}°
                  </div>

                  <!-- Centered Print Area Icon -->
                  <div class="w-full h-full pointer-events-none select-none flex items-center justify-center">
                    <div class="size-7 rounded-lg bg-primary/90 text-white flex items-center justify-center shadow-md backdrop-blur-xs">
                      <Icon name="lucide:sparkles" class="size-4" aria-hidden="true" />
                    </div>
                  </div>

                  <!-- Corner Resize Handle -->
                  <div
                    class="absolute -bottom-1.5 -right-1.5 size-4.5 bg-primary border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                    title="Drag to resize print area"
                    @pointerdown="onResizePointerDown"
                  >
                    <Icon name="lucide:maximize-2" class="size-2 text-white" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>

            <p class="text-[11px] text-muted-foreground text-center">
              💡 Drag box to move · Drag bottom-right corner to scale · Drag top handle or use sliders to rotate
            </p>
          </div>

          <!-- Right Column (5 cols): Placement Precision Controls & Metadata -->
          <div class="lg:col-span-5 space-y-4">
            <div class="space-y-1.5">
              <Label class="text-xs font-bold text-foreground">Template Name</Label>
              <Input v-model="editName" class="h-8.5 text-xs" />
            </div>

            <div class="space-y-1.5">
              <Label class="text-xs font-bold text-foreground">Product Category</Label>
              <select
                v-model="editProductType"
                class="flex h-8.5 w-full rounded-lg border border-border bg-white px-3 py-1.5 text-xs shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary text-foreground font-medium"
              >
                <option v-for="opt in allCategoryOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <!-- Precision Sliders Card -->
            <div class="p-3.5 bg-secondary/40 rounded-xl border border-border space-y-3">
              <div class="flex items-center justify-between text-[11px] font-bold text-foreground uppercase tracking-wider">
                <span class="flex items-center gap-1.5">
                  <Icon name="lucide:sliders" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Placement &amp; Rotation</span>
                </span>
                <button
                  type="button"
                  class="text-[10px] text-primary hover:underline font-semibold cursor-pointer lowercase"
                  @click="centerEditPlacement(); setEditAngle(0)"
                >
                  reset placement
                </button>
              </div>

              <div class="space-y-2.5">
                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Box Width</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(editPlacement.width_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="editPlacement.width_pct" type="range" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Box Height</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(editPlacement.height_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="editPlacement.height_pct" type="range" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Horizontal (X)</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(editPlacement.left_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="editPlacement.left_pct" type="range" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Vertical (Y)</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(editPlacement.top_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="editPlacement.top_pct" type="range" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <!-- Rotation Angle Slider & Quick Angle Buttons -->
                <div class="space-y-1.5 pt-2 border-t border-border/60">
                  <div class="flex justify-between items-center text-[11px]">
                    <span class="text-secondary-foreground font-semibold flex items-center gap-1">
                      <Icon name="lucide:rotate-cw" class="size-3 text-primary" aria-hidden="true" />
                      <span>Rotation Angle</span>
                    </span>
                    <span class="font-mono font-bold text-foreground bg-white dark:bg-slate-900 px-1.5 py-0.5 rounded border border-border text-[10px]">
                      {{ editPlacement.angle_deg || 0 }}°
                    </span>
                  </div>
                  <input
                    v-model.number="editPlacement.angle_deg"
                    type="range"
                    min="-180"
                    max="180"
                    step="1"
                    class="w-full h-1.5 accent-primary cursor-pointer"
                  >
                  <div class="flex items-center justify-between gap-1 pt-0.5">
                    <button
                      v-for="deg in [-90, -45, 0, 45, 90]"
                      :key="deg"
                      type="button"
                      class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition-all cursor-pointer"
                      :class="editPlacement.angle_deg === deg ? 'bg-primary text-white shadow-2xs font-bold' : 'bg-white dark:bg-slate-900 text-muted-foreground hover:text-foreground border border-border'"
                      @click="setEditAngle(deg)"
                    >
                      {{ deg > 0 ? `+${deg}°` : `${deg}°` }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Texture Blend Mode Section -->
            <div class="space-y-2 pt-1">
              <div class="flex items-center justify-between">
                <Label class="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Icon name="lucide:palette" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Texture Blend Mode</span>
                </Label>
                <Badge variant="outline" class="text-[10px] font-mono font-bold uppercase">
                  {{ getBlendModeInfo(editPlacement.blend_mode).shortLabel }}
                </Badge>
              </div>

              <!-- Blend Mode Grid -->
              <div class="grid grid-cols-2 gap-1.5">
                <button
                  v-for="opt in BLEND_MODE_OPTIONS"
                  :key="opt.value"
                  type="button"
                  class="flex flex-col text-left p-2 rounded-xl border transition-all cursor-pointer relative"
                  :class="[
                    editPlacement.blend_mode === opt.value
                      ? 'bg-primary/5 border-primary ring-1 ring-primary shadow-2xs'
                      : 'bg-white border-border/80 hover:border-slate-300 hover:bg-slate-50/50'
                  ]"
                  @click="editPlacement.blend_mode = opt.value"
                >
                  <div class="flex items-center justify-between gap-1 w-full mb-1">
                    <span class="text-[11px] font-bold truncate" :class="editPlacement.blend_mode === opt.value ? 'text-primary font-bold' : 'text-foreground'">
                      {{ opt.shortLabel }}
                    </span>
                    <Icon
                      :name="opt.iconName"
                      class="size-3 shrink-0"
                      :class="editPlacement.blend_mode === opt.value ? 'text-primary' : 'text-muted-foreground'"
                      aria-hidden="true"
                    />
                  </div>
                  <span class="text-[10px] text-muted-foreground line-clamp-1 leading-tight">
                    {{ opt.badge }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <Alert v-if="updateError" variant="destructive" class="mx-5 mb-2">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ updateError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 p-4 sm:p-5 border-t border-border bg-card/50">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" :disabled="isUpdating" @click="templateToEdit = null">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold gap-1 cursor-pointer"
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
      class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-200"
      @click.self="showUploadModal = false"
    >
      <div class="bg-card rounded-2xl shadow-2xl border border-border max-w-5xl w-full flex flex-col max-h-[92vh] overflow-hidden">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-border p-4 sm:p-5 bg-card/50">
          <div class="flex items-center gap-3">
            <div class="size-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 shadow-2xs">
              <Icon name="lucide:upload" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <h3 class="text-base sm:text-lg font-bold text-foreground">Upload Mockup Template &amp; Set Placement</h3>
              <p class="text-xs text-muted-foreground">
                {{ uploadStep === 'file' ? 'Step 1 of 3: Select blank mockup image' : uploadStep === 'crop' ? 'Step 2 of 3: Crop and frame photo' : 'Step 3 of 3: Position print boundary and rotation' }}
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <!-- Step navigation indicators -->
            <div class="hidden sm:flex items-center gap-1 bg-secondary/60 p-1 rounded-lg border border-border text-[11px] font-semibold">
              <span
                class="px-2 py-0.5 rounded-md transition-all"
                :class="uploadStep === 'file' ? 'bg-white text-primary shadow-2xs font-bold' : 'text-muted-foreground'"
              >
                1. Select
              </span>
              <Icon name="lucide:chevron-right" class="size-3 text-muted-foreground/60" />
              <span
                class="px-2 py-0.5 rounded-md transition-all"
                :class="uploadStep === 'crop' ? 'bg-white text-primary shadow-2xs font-bold' : 'text-muted-foreground'"
              >
                2. Crop
              </span>
              <Icon name="lucide:chevron-right" class="size-3 text-muted-foreground/60" />
              <span
                class="px-2 py-0.5 rounded-md transition-all"
                :class="uploadStep === 'placement' ? 'bg-white text-primary shadow-2xs font-bold' : 'text-muted-foreground'"
              >
                3. Placement
              </span>
            </div>

            <button
              type="button"
              class="size-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
              @click="showUploadModal = false"
            >
              <Icon name="lucide:x" class="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <!-- Step 1: Drag & Drop File Selection Dropzone -->
        <div v-if="uploadStep === 'file'" class="p-6 sm:p-8 space-y-6">
          <div
            class="border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all duration-200 cursor-pointer flex flex-col items-center justify-center gap-4 relative group"
            :class="[
              isDraggingFile
                ? 'border-primary bg-primary/10 shadow-lg scale-[1.01]'
                : 'border-border/80 hover:border-primary/60 bg-secondary/20 hover:bg-secondary/40'
            ]"
            @dragover.prevent="onFileDragOver"
            @dragleave.prevent="onFileDragLeave"
            @drop.prevent="onFileDrop"
            @click="fileInputRef?.click()"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="hidden"
              @change="handleFileSelect"
            >

            <div class="size-16 rounded-2xl bg-white shadow-md border border-border flex items-center justify-center text-primary group-hover:scale-110 group-hover:text-primary transition-all">
              <Icon name="lucide:cloud-upload" class="size-8" aria-hidden="true" />
            </div>

            <div class="space-y-1.5 max-w-sm mx-auto">
              <h4 class="text-base font-bold text-foreground">
                Choose a Mockup Photo or Drag &amp; Drop Here
              </h4>
              <p class="text-xs text-muted-foreground">
                Upload a clean, high-resolution blank product photo (t-shirt, mug, tote bag, poster, etc.)
              </p>
            </div>

            <div class="flex items-center gap-2 flex-wrap justify-center pt-2">
              <Badge variant="secondary" class="text-[11px] px-2.5 py-0.5 font-medium">PNG</Badge>
              <Badge variant="secondary" class="text-[11px] px-2.5 py-0.5 font-medium">JPEG</Badge>
              <Badge variant="secondary" class="text-[11px] px-2.5 py-0.5 font-medium">WEBP</Badge>
              <span class="text-[11px] text-muted-foreground ml-1">Up to 20MB · Recommended 2000×2000 px+</span>
            </div>
          </div>
        </div>

        <!-- Step 2: Inline Photo Cropper -->
        <div v-else-if="uploadStep === 'crop'" class="p-5 flex-1 overflow-y-auto">
          <ImageCropperView
            :image-url="rawUploadFileUrl || uploadImagePreviewUrl"
            :file-name="uploadImageFile?.name"
            @crop="handleUploadCropComplete"
            @cancel="uploadStep = 'placement'"
          />
        </div>

        <!-- Step 3: Visual Placement Studio -->
        <div v-else class="grid grid-cols-1 lg:grid-cols-12 gap-5 overflow-y-auto flex-1 p-5 items-start">
          <!-- Left Column (7 cols): Interactive Visual Canvas -->
          <div class="lg:col-span-7 space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Icon name="lucide:layout" class="size-3.5 text-primary" aria-hidden="true" />
                <span>Designate PNG Print Area</span>
              </span>

              <!-- Quick Placement & Rotation Segmented Toolbar -->
              <div class="flex items-center gap-1.5 flex-wrap">
                <button
                  type="button"
                  class="px-2.5 py-1 text-[11px] font-bold bg-blue-50 hover:bg-blue-100 text-primary rounded-lg transition-all cursor-pointer border border-blue-200 shadow-2xs hover:shadow-xs inline-flex items-center gap-1.5"
                  title="Crop template photo"
                  @click="uploadStep = 'crop'"
                >
                  <Icon name="lucide:crop" class="size-3.5" aria-hidden="true" />
                  <span>Crop / Cut</span>
                </button>

                <div class="flex items-center gap-1 bg-secondary/80 p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Center artwork box"
                    @click="centerUploadPlacement"
                  >
                    <Icon name="lucide:align-center" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Center</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply full center preset"
                    @click="applyUploadFullCenterPreset"
                  >
                    <Icon name="lucide:maximize-2" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Full</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply left chest preset"
                    @click="applyUploadChestPreset"
                  >
                    <Icon name="lucide:target" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Chest</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
                    title="Apply square 1:1 preset"
                    @click="applyUploadSquarePreset"
                  >
                    <Icon name="lucide:square" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>1:1</span>
                  </button>
                </div>

                <!-- Rotation Quick Buttons -->
                <div class="flex items-center gap-1 bg-secondary/80 p-0.5 rounded-lg border border-border shadow-2xs">
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Rotate 90 degrees counter-clockwise"
                    @click="rotateUploadLeft"
                  >
                    <Icon name="lucide:rotate-ccw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>-90°</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-secondary-foreground hover:text-primary hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Rotate 90 degrees clockwise"
                    @click="rotateUploadRight"
                  >
                    <Icon name="lucide:rotate-cw" class="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>+90°</span>
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground hover:bg-white rounded-md transition-all cursor-pointer inline-flex items-center gap-1 shadow-2xs hover:shadow-xs"
                    title="Reset rotation to 0°"
                    @click="setUploadAngle(0)"
                  >
                    <span>0°</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Canvas Viewport Frame -->
            <div class="relative w-full max-h-[380px] bg-slate-950/90 rounded-2xl border border-slate-800 overflow-hidden flex items-center justify-center p-3 shadow-inner min-h-[260px]">
              <!-- Exact Image-Fitting Upload Canvas -->
              <div
                v-if="uploadImagePreviewUrl"
                ref="uploadCanvasRef"
                class="relative inline-block select-none touch-none max-h-[350px] max-w-full"
              >
                <img
                  :src="uploadImagePreviewUrl"
                  alt="Upload Preview"
                  class="max-h-[350px] max-w-full w-auto h-auto block rounded-lg pointer-events-none object-contain shadow-md"
                >

                <!-- Alignment Crosshairs -->
                <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 border-t border-dashed border-primary/30 pointer-events-none" />
                <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-primary/30 pointer-events-none" />

                <!-- Draggable, Resizable & Rotatable Placement Box -->
                <div
                  class="absolute border-2 border-primary bg-primary/20 backdrop-blur-[0.5px] cursor-grab active:cursor-grabbing flex items-center justify-center rounded-xs transition-shadow shadow-md hover:ring-2 hover:ring-primary/50 select-none"
                  :style="{
                    left: `${uploadPlacement.left_pct * 100}%`,
                    top: `${uploadPlacement.top_pct * 100}%`,
                    width: `${uploadPlacement.width_pct * 100}%`,
                    height: `${uploadPlacement.height_pct * 100}%`,
                    transform: `rotate(${uploadPlacement.angle_deg || 0}deg)`,
                    transformOrigin: 'center center',
                  }"
                  @pointerdown="onUploadArtworkPointerDown"
                >
                  <!-- Top Rotation Stalk & Handle -->
                  <div class="absolute -top-7 left-1/2 -translate-x-1/2 flex flex-col items-center pointer-events-auto select-none">
                    <div
                      class="size-5 rounded-full bg-primary text-white border-2 border-white shadow-md flex items-center justify-center cursor-grab active:cursor-grabbing hover:scale-125 transition-transform"
                      title="Drag to rotate print area"
                      @pointerdown="onUploadRotatePointerDown"
                    >
                      <Icon name="lucide:rotate-cw" class="size-2.5 text-white" aria-hidden="true" />
                    </div>
                    <div class="w-0.5 h-2 bg-primary/70" />
                  </div>

                  <!-- Live Coordinates Pill -->
                  <div class="absolute -top-12 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-slate-900/90 text-white rounded-md text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-md border border-slate-700/60">
                    {{ Math.round(uploadPlacement.left_pct * 100) }}%, {{ Math.round(uploadPlacement.top_pct * 100) }}% · {{ Math.round(uploadPlacement.width_pct * 100) }}×{{ Math.round(uploadPlacement.height_pct * 100) }}% · {{ uploadPlacement.angle_deg || 0 }}°
                  </div>

                  <!-- Centered Print Area Icon -->
                  <div class="w-full h-full pointer-events-none select-none flex items-center justify-center">
                    <div class="size-7 rounded-lg bg-primary/90 text-white flex items-center justify-center shadow-md backdrop-blur-xs">
                      <Icon name="lucide:sparkles" class="size-4" aria-hidden="true" />
                    </div>
                  </div>

                  <!-- Corner Resize Handle -->
                  <div
                    class="absolute -bottom-1.5 -right-1.5 size-4.5 bg-primary border-2 border-white rounded-full cursor-nwse-resize hover:scale-125 transition-transform flex items-center justify-center shadow-md touch-none"
                    title="Drag to resize print area"
                    @pointerdown="onUploadResizePointerDown"
                  >
                    <Icon name="lucide:maximize-2" class="size-2 text-white" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>

            <p class="text-[11px] text-muted-foreground text-center">
              💡 Drag to position · Drag corner handle to resize · Drag top handle or use sliders to rotate
            </p>
          </div>

          <!-- Right Column (5 cols): Metadata & Category -->
          <div class="lg:col-span-5 space-y-4">
            <div class="space-y-1.5">
              <Label class="text-xs font-bold text-foreground">Template Name</Label>
              <Input v-model="uploadName" placeholder="e.g. Vintage Mug on Marble Table" class="h-8.5 text-xs" />
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <Label class="text-xs font-bold text-foreground">Product Category</Label>
                <button
                  v-if="!showCategoryDropdown && selectedCategory !== 'all'"
                  type="button"
                  class="text-[11px] font-semibold text-primary hover:text-primary-hover cursor-pointer"
                  @click="showCategoryDropdown = true"
                >
                  Change Category
                </button>
              </div>

              <!-- Locked Pre-Selected Category Pill -->
              <div
                v-if="!showCategoryDropdown && selectedCategory !== 'all'"
                class="flex items-center justify-between p-2 rounded-lg bg-secondary/50 border border-border text-xs font-semibold text-foreground shadow-2xs"
              >
                <div class="flex items-center gap-2">
                  <div class="size-6 rounded-md bg-white flex items-center justify-center text-primary shadow-2xs border border-border">
                    <Icon :name="getProductIconName(uploadProductType)" class="size-3.5" aria-hidden="true" />
                  </div>
                  <span>{{ getProductLabel(uploadProductType) }}</span>
                </div>
                <Badge variant="outline" class="text-[10px] bg-white text-secondary-foreground border-border">
                  Current Tab
                </Badge>
              </div>

              <!-- Full Category Selector Dropdown -->
              <select
                v-else
                v-model="uploadProductType"
                class="flex h-8.5 w-full rounded-lg border border-border bg-white px-3 py-1.5 text-xs shadow-2xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary text-foreground font-medium"
              >
                <option v-for="opt in allCategoryOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
                <option value="custom">+ New Custom Product Category...</option>
              </select>
            </div>

            <div v-if="showCategoryDropdown && uploadProductType === 'custom'" class="space-y-1.5 animate-in fade-in">
              <Label class="text-xs font-bold text-primary">Custom Category Name</Label>
              <Input v-model="uploadCustomTypeName" placeholder="e.g. Canvas Print, Pillow, Blanket" class="h-8.5 text-xs border-border" />
            </div>

            <!-- Precision Sliders Card -->
            <div class="p-3.5 bg-secondary/40 rounded-xl border border-border space-y-3">
              <div class="flex items-center justify-between text-[11px] font-bold text-foreground uppercase tracking-wider">
                <span class="flex items-center gap-1.5">
                  <Icon name="lucide:sliders" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Placement &amp; Rotation</span>
                </span>
                <button
                  type="button"
                  class="text-[10px] text-primary hover:underline font-semibold cursor-pointer lowercase"
                  @click="centerUploadPlacement(); setUploadAngle(0)"
                >
                  reset placement
                </button>
              </div>

              <div class="space-y-2.5">
                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Box Width</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(uploadPlacement.width_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="uploadPlacement.width_pct" type="range" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Box Height</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(uploadPlacement.height_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="uploadPlacement.height_pct" type="range" min="0.1" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Horizontal (X)</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(uploadPlacement.left_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="uploadPlacement.left_pct" type="range" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <div class="space-y-1">
                  <div class="flex justify-between text-[11px]">
                    <span class="text-secondary-foreground font-medium">Vertical (Y)</span>
                    <span class="font-mono font-bold text-foreground">{{ Math.round(uploadPlacement.top_pct * 100) }}%</span>
                  </div>
                  <input v-model.number="uploadPlacement.top_pct" type="range" min="0.0" max="0.9" step="0.01" class="w-full h-1.5 accent-primary cursor-pointer">
                </div>

                <!-- Rotation Angle Slider & Quick Angle Buttons -->
                <div class="space-y-1.5 pt-2 border-t border-border/60">
                  <div class="flex justify-between items-center text-[11px]">
                    <span class="text-secondary-foreground font-semibold flex items-center gap-1">
                      <Icon name="lucide:rotate-cw" class="size-3 text-primary" aria-hidden="true" />
                      <span>Rotation Angle</span>
                    </span>
                    <span class="font-mono font-bold text-foreground bg-white dark:bg-slate-900 px-1.5 py-0.5 rounded border border-border text-[10px]">
                      {{ uploadPlacement.angle_deg || 0 }}°
                    </span>
                  </div>
                  <input
                    v-model.number="uploadPlacement.angle_deg"
                    type="range"
                    min="-180"
                    max="180"
                    step="1"
                    class="w-full h-1.5 accent-primary cursor-pointer"
                  >
                  <div class="flex items-center justify-between gap-1 pt-0.5">
                    <button
                      v-for="deg in [-90, -45, 0, 45, 90]"
                      :key="deg"
                      type="button"
                      class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition-all cursor-pointer"
                      :class="uploadPlacement.angle_deg === deg ? 'bg-primary text-white shadow-2xs font-bold' : 'bg-white dark:bg-slate-900 text-muted-foreground hover:text-foreground border border-border'"
                      @click="setUploadAngle(deg)"
                    >
                      {{ deg > 0 ? `+${deg}°` : `${deg}°` }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Texture Blend Mode Section -->
            <div class="space-y-2 pt-1">
              <div class="flex items-center justify-between">
                <Label class="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Icon name="lucide:palette" class="size-3.5 text-primary" aria-hidden="true" />
                  <span>Texture Blend Mode</span>
                </Label>
                <Badge variant="outline" class="text-[10px] font-mono font-bold uppercase">
                  {{ getBlendModeInfo(uploadPlacement.blend_mode).shortLabel }}
                </Badge>
              </div>

              <!-- Blend Mode Grid -->
              <div class="grid grid-cols-2 gap-1.5">
                <button
                  v-for="opt in BLEND_MODE_OPTIONS"
                  :key="opt.value"
                  type="button"
                  class="flex flex-col text-left p-2 rounded-xl border transition-all cursor-pointer relative"
                  :class="[
                    uploadPlacement.blend_mode === opt.value
                      ? 'bg-primary/5 border-primary ring-1 ring-primary shadow-2xs'
                      : 'bg-white border-border/80 hover:border-slate-300 hover:bg-slate-50/50'
                  ]"
                  @click="uploadPlacement.blend_mode = opt.value"
                >
                  <div class="flex items-center justify-between gap-1 w-full mb-1">
                    <span class="text-[11px] font-bold truncate" :class="uploadPlacement.blend_mode === opt.value ? 'text-primary font-bold' : 'text-foreground'">
                      {{ opt.shortLabel }}
                    </span>
                    <Icon
                      :name="opt.iconName"
                      class="size-3 shrink-0"
                      :class="uploadPlacement.blend_mode === opt.value ? 'text-primary' : 'text-muted-foreground'"
                      aria-hidden="true"
                    />
                  </div>
                  <span class="text-[10px] text-muted-foreground line-clamp-1 leading-tight">
                    {{ opt.badge }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <Alert v-if="uploadError" variant="destructive" class="mx-5 mb-2">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ uploadError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 p-4 sm:p-5 border-t border-border bg-card/50">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" :disabled="isUploading" @click="showUploadModal = false">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold gap-1 cursor-pointer"
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
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200"
      @click.self="showAddCustomTypeModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-border max-w-sm w-full p-6 space-y-4">
        <div class="flex items-center justify-between border-b border-border pb-3">
          <div class="flex items-center gap-2">
            <Icon name="lucide:plus-circle" class="size-4 text-primary" aria-hidden="true" />
            <h3 class="text-sm font-bold text-foreground">Add Custom Product Category</h3>
          </div>
          <button type="button" class="text-muted-foreground hover:text-foreground cursor-pointer" @click="showAddCustomTypeModal = false">
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <div class="space-y-2">
          <Label class="text-xs font-bold">Product Category Name</Label>
          <Input v-model="newCustomTypeName" placeholder="e.g. Canvas Print, Phone Grip, Pillow" class="h-9 text-xs" />
          <p class="text-[11px] text-muted-foreground">This category will appear in your Mockup Library tabs and Intended Physical Products.</p>
        </div>

        <div class="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="outline" size="sm" class="text-xs cursor-pointer" @click="showAddCustomTypeModal = false">
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold gap-1 cursor-pointer"
            :disabled="!newCustomTypeName.trim()"
            @click="handleAddCustomProductType"
          >
            <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
            <span>Add Category</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Modal: Delete Category & all its Mockups -->
    <div
      v-if="showDeleteCategoryModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200"
      @click.self="showDeleteCategoryModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-border max-w-md w-full p-6 space-y-4">
        <div class="flex items-start gap-3">
          <div class="h-10 w-10 rounded-xl bg-red-50 text-destructive flex items-center justify-center shrink-0 border border-red-200">
            <Icon name="lucide:trash-2" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <h4 class="text-sm font-bold text-foreground">
              Delete {{ categoryToDelete ? getProductLabel(categoryToDelete) : 'Category' }}?
            </h4>
            <p class="text-xs text-muted-foreground mt-1 leading-relaxed">
              Are you sure you want to delete this product category and all its
              <strong class="text-foreground font-semibold">{{ categoryToDelete ? (templateCounts[categoryToDelete] || 0) : 0 }} mockup templates</strong>?
              This will permanently delete the mockup photos and placement manifests from storage.
            </p>
          </div>
        </div>

        <Alert v-if="deleteCategoryError" variant="destructive">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertDescription>{{ deleteCategoryError }}</AlertDescription>
        </Alert>

        <div class="flex justify-end gap-2 pt-2 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            class="text-xs cursor-pointer"
            :disabled="isDeletingCategory"
            @click="showDeleteCategoryModal = false"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            class="text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
            :disabled="isDeletingCategory"
            @click="confirmDeleteCategory"
          >
            <Icon v-if="isDeletingCategory" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
            <span>{{ isDeletingCategory ? 'Deleting...' : 'Delete Category & Mockups' }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
