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
  blendMode: "multiply" | "over" | "screen" | "overlay" | "darken" | "lighten";
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

const blendStyle = computed(() => {
  return {
    mixBlendMode: props.blendMode === "multiply" ? ("multiply" as const) : ("normal" as const),
  };
});
</script>

<template>
  <div class="relative w-full aspect-square bg-zinc-950 rounded-2xl overflow-hidden shadow-inner flex items-center justify-center select-none p-2">
    <!-- Template Aspect-Ratio Sized Container with 1:1 Pixel Mapping -->
    <div
      ref="containerRef"
      class="relative max-w-full max-h-full overflow-hidden rounded-lg flex items-center justify-center shadow-lg"
      :style="imageAspectRatio ? { aspectRatio: `${imageAspectRatio}` } : { width: '100%', height: '100%' }"
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

      <!-- Artwork Placement Interactive Overlay -->
      <div
        v-if="templateImageUrl && masterImageUrl"
        class="absolute cursor-move transition-[box-shadow]"
        :class="
          viewMode === 'edit'
            ? 'border-2 border-dashed border-primary bg-primary/10 shadow-lg'
            : 'border-0 bg-transparent'
        "
        :style="artworkBoxStyle"
        @mousedown="startDrag"
      >
        <!-- Master PNG Artwork Inside Placement Box -->
        <img
          :src="masterImageUrl"
          alt="Artwork Preview"
          class="w-full h-full object-contain pointer-events-none transition-all select-none"
          :style="blendStyle"
        >

        <!-- Resize Handle in Bottom Right -->
        <div
          v-if="viewMode === 'edit'"
          class="absolute -bottom-2 -right-2 h-5 w-5 bg-primary border-2 border-white rounded-full cursor-nwse-resize shadow-md flex items-center justify-center hover:scale-125 transition-transform"
          @mousedown="startResize"
        >
          <div class="h-1.5 w-1.5 bg-white rounded-full" />
        </div>

        <!-- Center Crosshair for Edit Mode -->
        <div
          v-if="viewMode === 'edit'"
          class="absolute inset-0 pointer-events-none flex items-center justify-center opacity-40"
        >
          <div class="w-2 h-0.5 bg-primary absolute" />
          <div class="h-2 w-0.5 bg-primary absolute" />
        </div>
      </div>
    </div>
  </div>
</template>
