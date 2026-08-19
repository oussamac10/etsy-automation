<script setup lang="ts">
import { ref, computed, watch } from "vue";

const props = defineProps<{
  templateImageUrl: string | null;
  masterImageUrl: string | null;
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  angleDeg: number;
  blendMode: "multiply" | "over" | "screen" | "overlay" | "soft-light" | "hard-light" | "darken" | "lighten" | string;
  viewMode: "edit" | "preview";
}>();

const emit = defineEmits<{
  (e: "update:leftPct", val: number): void;
  (e: "update:topPct", val: number): void;
  (e: "update:widthPct", val: number): void;
  (e: "update:heightPct", val: number): void;
  (e: "update:angleDeg", val: number): void;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const imageAspectRatio = ref<number | null>(null);
const isDragging = ref(false);
const isResizing = ref(false);

let startX = 0;
let startY = 0;
let initLeft = 25;
let initTop = 25;
let initWidth = 50;
let initHeight = 50;

function handleImageLoaded(e: Event): void {
  const img = e.target as HTMLImageElement;
  if (img.naturalWidth && img.naturalHeight) {
    imageAspectRatio.value = img.naturalWidth / img.naturalHeight;
  }
}

watch(
  () => props.templateImageUrl,
  (newUrl) => {
    if (!newUrl) {
      imageAspectRatio.value = null;
      return;
    }
    const testImg = new Image();
    testImg.onload = () => {
      if (testImg.naturalWidth && testImg.naturalHeight) {
        imageAspectRatio.value = testImg.naturalWidth / testImg.naturalHeight;
      }
    };
    testImg.src = newUrl;
  },
  { immediate: true }
);

function startDrag(e: MouseEvent): void {
  if (props.viewMode === "preview") return;
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = true;
  startX = e.clientX;
  startY = e.clientY;
  initLeft = props.leftPct;
  initTop = props.topPct;

  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

function onDragMove(e: MouseEvent): void {
  if (!isDragging.value || !containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  const dx = ((e.clientX - startX) / rect.width) * 100;
  const dy = ((e.clientY - startY) / rect.height) * 100;

  const newLeft = Math.max(0, Math.min(100 - props.widthPct, initLeft + dx));
  const newTop = Math.max(0, Math.min(100 - props.heightPct, initTop + dy));

  emit("update:leftPct", Math.round(newLeft * 10) / 10);
  emit("update:topPct", Math.round(newTop * 10) / 10);
}

function onDragEnd(): void {
  isDragging.value = false;
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", onDragEnd);
}

function startResize(e: MouseEvent): void {
  if (props.viewMode === "preview") return;
  e.preventDefault();
  e.stopPropagation();
  isResizing.value = true;
  startX = e.clientX;
  startY = e.clientY;
  initWidth = props.widthPct;
  initHeight = props.heightPct;

  window.addEventListener("mousemove", onResizeMove);
  window.addEventListener("mouseup", onResizeEnd);
}

function onResizeMove(e: MouseEvent): void {
  if (!isResizing.value || !containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  const dx = ((e.clientX - startX) / rect.width) * 100;
  const dy = ((e.clientY - startY) / rect.height) * 100;

  const delta = (dx + dy) / 2;
  const newWidth = Math.max(10, Math.min(100 - props.leftPct, initWidth + delta));
  const newHeight = Math.max(10, Math.min(100 - props.topPct, initHeight + delta));

  emit("update:widthPct", Math.round(newWidth * 10) / 10);
  emit("update:heightPct", Math.round(newHeight * 10) / 10);
}

function onResizeEnd(): void {
  isResizing.value = false;
  window.removeEventListener("mousemove", onResizeMove);
  window.removeEventListener("mouseup", onResizeEnd);
}

const artworkBoxStyle = computed(() => {
  return {
    left: `${props.leftPct}%`,
    top: `${props.topPct}%`,
    width: `${props.widthPct}%`,
    height: `${props.heightPct}%`,
    transform: `rotate(${props.angleDeg}deg)`,
    transformOrigin: "center center",
  };
});

const activeCssBlend = computed(() => {
  const norm = (props.blendMode || "over").toLowerCase().trim().replace(/_/g, "-");
  switch (norm) {
    case "multiply":
      return "multiply";
    case "screen":
      return "screen";
    case "overlay":
      return "overlay";
    case "soft-light":
      return "soft-light";
    case "hard-light":
      return "hard-light";
    case "darken":
      return "darken";
    case "lighten":
      return "lighten";
    case "color-burn":
      return "color-burn";
    case "color-dodge":
      return "color-dodge";
    case "over":
    default:
      return "normal";
  }
});
</script>

<template>
  <div class="relative w-full aspect-square bg-slate-900 rounded-2xl overflow-hidden shadow-inner flex items-center justify-center select-none p-2">
    <!-- Template Aspect-Ratio Sized Container with 1:1 Pixel Mapping & CSS Blend Isolation -->
    <div
      ref="containerRef"
      class="relative max-w-full max-h-full overflow-hidden rounded-lg flex items-center justify-center shadow-lg"
      :style="[
        imageAspectRatio ? { aspectRatio: `${imageAspectRatio}` } : { width: '100%', height: '100%' },
        { isolation: 'isolate' }
      ]"
    >
      <!-- Base Mockup Template Photo -->
      <img
        v-if="templateImageUrl"
        :src="templateImageUrl"
        alt="Mockup Template"
        class="w-full h-full object-contain pointer-events-none block select-none"
        @load="handleImageLoaded"
      >
      <div v-else class="text-zinc-500 text-xs py-12">No template selected</div>

      <!-- Layer 1: Pure Blended Master Artwork Container -->
      <div
        v-if="templateImageUrl && masterImageUrl"
        class="absolute pointer-events-none select-none"
        :style="[artworkBoxStyle, { mixBlendMode: activeCssBlend as any }]"
      >
        <img
          :src="masterImageUrl"
          alt="Artwork Preview"
          class="w-full h-full object-contain pointer-events-none select-none block"
        >
      </div>

      <!-- Layer 2: Interactive Controls & Placement Boundary (Only rendered in Edit mode) -->
      <div
        v-if="templateImageUrl && masterImageUrl && viewMode === 'edit'"
        class="absolute cursor-move border-2 border-dashed border-primary/90 bg-transparent shadow-sm select-none"
        :style="artworkBoxStyle"
        @mousedown="startDrag"
      >
        <!-- Resize Handle in Bottom Right -->
        <div
          class="absolute -bottom-2 -right-2 h-5 w-5 bg-primary border-2 border-white rounded-full cursor-nwse-resize shadow-md flex items-center justify-center hover:scale-125 transition-transform"
          @mousedown="startResize"
        >
          <div class="h-1.5 w-1.5 bg-white rounded-full" />
        </div>

        <!-- Center Crosshair for Edit Mode -->
        <div class="absolute inset-0 pointer-events-none flex items-center justify-center opacity-40">
          <div class="w-2 h-0.5 bg-primary absolute" />
          <div class="h-2 w-0.5 bg-primary absolute" />
        </div>
      </div>
    </div>
  </div>
</template>
