<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import type { MockupPlacement } from "~/types/mockup";

export interface ArtworkVariantOption {
  id: string;
  name: string;
  url: string;
}

const props = withDefaults(
  defineProps<{
    templateImageUrl: string | null;
    masterImageUrl: string | null;
    variants?: ArtworkVariantOption[];
    // Single placement backward compatibility props
    leftPct?: number;
    topPct?: number;
    widthPct?: number;
    heightPct?: number;
    angleDeg?: number;
    blendMode?: string;
    // Multi-placement props
    placements?: MockupPlacement[];
    activePlacementIndex?: number;
    viewMode?: "edit" | "preview";
  }>(),
  {
    variants: () => [],
    leftPct: 25,
    topPct: 25,
    widthPct: 50,
    heightPct: 50,
    angleDeg: 0,
    blendMode: "multiply",
    placements: undefined,
    activePlacementIndex: 0,
    viewMode: "edit",
  }
);

const emit = defineEmits<{
  (e: "update:leftPct", val: number): void;
  (e: "update:topPct", val: number): void;
  (e: "update:widthPct", val: number): void;
  (e: "update:heightPct", val: number): void;
  (e: "update:angleDeg", val: number): void;
  (e: "update:activePlacementIndex", val: number): void;
  (e: "updatePlacements", val: MockupPlacement[]): void;
  (e: "updateZonePlacement", payload: { index: number; placement: MockupPlacement }): void;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const imageAspectRatio = ref<number | null>(null);
const isDragging = ref(false);
const isResizing = ref(false);
const isRotating = ref(false);

let startX = 0;
let startY = 0;
let initLeft = 25;
let initTop = 25;
let initWidth = 50;
let initHeight = 50;

let rotateCenterScreenX = 0;
let rotateCenterScreenY = 0;
let rotateStartAngleRad = 0;
let initialAngleDeg = 0;

// Normalized zones list
const activeZones = computed<MockupPlacement[]>(() => {
  if (props.placements && props.placements.length > 0) {
    return props.placements;
  }
  return [
    {
      id: "zone-1",
      left_pct: props.leftPct <= 1.0 ? props.leftPct * 100 : props.leftPct,
      top_pct: props.topPct <= 1.0 ? props.topPct * 100 : props.topPct,
      width_pct: props.widthPct <= 1.0 ? props.widthPct * 100 : props.widthPct,
      height_pct: props.heightPct <= 1.0 ? props.heightPct * 100 : props.heightPct,
      angle_deg: props.angleDeg,
      blend_mode: props.blendMode,
    },
  ];
});

const currentZoneIndex = computed(() => {
  const maxIdx = Math.max(0, activeZones.value.length - 1);
  return Math.min(Math.max(0, props.activePlacementIndex), maxIdx);
});

const currentZone = computed<MockupPlacement>(() => {
  return (
    activeZones.value[currentZoneIndex.value] || {
      id: "zone-1",
      left_pct: 25,
      top_pct: 25,
      width_pct: 50,
      height_pct: 50,
      angle_deg: 0,
      blend_mode: "multiply",
    }
  );
});

function getZoneLeftPct(zone: MockupPlacement): number {
  const val = zone.left_pct ?? 25;
  return val <= 1.0 ? val * 100 : val;
}

function getZoneTopPct(zone: MockupPlacement): number {
  const val = zone.top_pct ?? 25;
  return val <= 1.0 ? val * 100 : val;
}

function getZoneWidthPct(zone: MockupPlacement): number {
  const val = zone.width_pct ?? 50;
  return val <= 1.0 ? val * 100 : val;
}

function getZoneHeightPct(zone: MockupPlacement): number {
  const val = zone.height_pct ?? 50;
  return val <= 1.0 ? val * 100 : val;
}

function getZoneArtworkUrl(zone: MockupPlacement): string | null {
  if (zone.artwork_source_id && props.variants?.length) {
    const found = props.variants.find((v) => v.id === zone.artwork_source_id);
    if (found?.url) return found.url;
  }
  return props.masterImageUrl || null;
}

function resolveCssBlend(blendMode: string | undefined): string {
  const norm = (blendMode || "multiply").toLowerCase().trim().replace(/_/g, "-");
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
}

function getBoxStyle(zone: MockupPlacement) {
  return {
    left: `${getZoneLeftPct(zone)}%`,
    top: `${getZoneTopPct(zone)}%`,
    width: `${getZoneWidthPct(zone)}%`,
    height: `${getZoneHeightPct(zone)}%`,
    transform: `rotate(${zone.angle_deg || 0}deg)`,
    transformOrigin: "center center",
  };
}

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

function selectZone(idx: number, e?: MouseEvent): void {
  if (e) {
    e.stopPropagation();
  }
  emit("update:activePlacementIndex", idx);
}

function emitZoneUpdate(updatedZone: MockupPlacement): void {
  const idx = currentZoneIndex.value;
  // Single prop backward compatibility
  emit("update:leftPct", updatedZone.left_pct);
  emit("update:topPct", updatedZone.top_pct);
  emit("update:widthPct", updatedZone.width_pct);
  emit("update:heightPct", updatedZone.height_pct);
  emit("update:angleDeg", updatedZone.angle_deg);

  // Multi placement emits
  emit("updateZonePlacement", { index: idx, placement: updatedZone });
  if (props.placements && props.placements.length > 0) {
    const nextList = [...props.placements];
    nextList[idx] = updatedZone;
    emit("updatePlacements", nextList);
  }
}

function startDrag(e: MouseEvent): void {
  if (props.viewMode === "preview") return;
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = true;
  startX = e.clientX;
  startY = e.clientY;
  initLeft = getZoneLeftPct(currentZone.value);
  initTop = getZoneTopPct(currentZone.value);

  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

function onDragMove(e: MouseEvent): void {
  if (!isDragging.value || !containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  const dx = ((e.clientX - startX) / rect.width) * 100;
  const dy = ((e.clientY - startY) / rect.height) * 100;

  const w = getZoneWidthPct(currentZone.value);
  const h = getZoneHeightPct(currentZone.value);
  const newLeft = Math.max(0, Math.min(100 - w, initLeft + dx));
  const newTop = Math.max(0, Math.min(100 - h, initTop + dy));

  const updated: MockupPlacement = {
    ...currentZone.value,
    left_pct: Math.round(newLeft * 10) / 10,
    top_pct: Math.round(newTop * 10) / 10,
  };
  emitZoneUpdate(updated);
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
  initWidth = getZoneWidthPct(currentZone.value);
  initHeight = getZoneHeightPct(currentZone.value);

  window.addEventListener("mousemove", onResizeMove);
  window.addEventListener("mouseup", onResizeEnd);
}

function onResizeMove(e: MouseEvent): void {
  if (!isResizing.value || !containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  const dx = ((e.clientX - startX) / rect.width) * 100;
  const dy = ((e.clientY - startY) / rect.height) * 100;

  const delta = (dx + dy) / 2;
  const l = getZoneLeftPct(currentZone.value);
  const t = getZoneTopPct(currentZone.value);
  const newWidth = Math.max(8, Math.min(100 - l, initWidth + delta));
  const newHeight = Math.max(8, Math.min(100 - t, initHeight + delta));

  const updated: MockupPlacement = {
    ...currentZone.value,
    width_pct: Math.round(newWidth * 10) / 10,
    height_pct: Math.round(newHeight * 10) / 10,
  };
  emitZoneUpdate(updated);
}

function onResizeEnd(): void {
  isResizing.value = false;
  window.removeEventListener("mousemove", onResizeMove);
  window.removeEventListener("mouseup", onResizeEnd);
}

function startRotate(e: PointerEvent): void {
  if (props.viewMode === "preview" || !containerRef.value) return;
  e.preventDefault();
  e.stopPropagation();
  isRotating.value = true;

  const rect = containerRef.value.getBoundingClientRect();
  const l = getZoneLeftPct(currentZone.value);
  const t = getZoneTopPct(currentZone.value);
  const w = getZoneWidthPct(currentZone.value);
  const h = getZoneHeightPct(currentZone.value);

  const boxCenterX = rect.left + (l + w / 2) * (rect.width / 100);
  const boxCenterY = rect.top + (t + h / 2) * (rect.height / 100);

  rotateCenterScreenX = boxCenterX;
  rotateCenterScreenY = boxCenterY;
  rotateStartAngleRad = Math.atan2(e.clientY - boxCenterY, e.clientX - boxCenterX);
  initialAngleDeg = currentZone.value.angle_deg || 0;

  window.addEventListener("pointermove", onRotateMove);
  window.addEventListener("pointerup", onRotateEnd);
}

function onRotateMove(e: PointerEvent): void {
  if (!isRotating.value) return;
  const currentAngleRad = Math.atan2(e.clientY - rotateCenterScreenY, e.clientX - rotateCenterScreenX);
  const deltaDeg = (currentAngleRad - rotateStartAngleRad) * (180 / Math.PI);
  let newAngle = Math.round(initialAngleDeg + deltaDeg);
  while (newAngle > 180) newAngle -= 360;
  while (newAngle < -180) newAngle += 360;

  const updated: MockupPlacement = {
    ...currentZone.value,
    angle_deg: newAngle,
  };
  emitZoneUpdate(updated);
}

function onRotateEnd(): void {
  isRotating.value = false;
  window.removeEventListener("pointermove", onRotateMove);
  window.removeEventListener("pointerup", onRotateEnd);
}

function handleKeyDown(e: KeyboardEvent): void {
  if (props.viewMode === "preview" || !props.templateImageUrl) return;

  // Don't intercept if user is typing in an input, textarea, or contentEditable
  const target = e.target as HTMLElement | null;
  const isInput =
    target &&
    (target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable);
  if (isInput) return;

  const key = e.key;
  const isShift = e.shiftKey;
  const isAlt = e.altKey;

  // Step sizes: default 1%, Shift 5% for fast, Alt 0.2% for ultra-precision
  const posStep = isShift ? 5 : isAlt ? 0.2 : 1;
  const sizeStep = isShift ? 5 : isAlt ? 0.5 : 1;
  const rotStep = isShift ? 15 : isAlt ? 1 : 5;

  let handled = false;
  const curr = currentZone.value;
  const l = getZoneLeftPct(curr);
  const t = getZoneTopPct(curr);
  const w = getZoneWidthPct(curr);
  const h = getZoneHeightPct(curr);
  const angle = curr.angle_deg || 0;

  if (key === "ArrowUp") {
    const newTop = Math.max(0, Math.min(100 - h, t - posStep));
    emitZoneUpdate({
      ...curr,
      top_pct: Math.round(newTop * 10) / 10,
    });
    handled = true;
  } else if (key === "ArrowDown") {
    const newTop = Math.max(0, Math.min(100 - h, t + posStep));
    emitZoneUpdate({
      ...curr,
      top_pct: Math.round(newTop * 10) / 10,
    });
    handled = true;
  } else if (key === "ArrowLeft") {
    const newLeft = Math.max(0, Math.min(100 - w, l - posStep));
    emitZoneUpdate({
      ...curr,
      left_pct: Math.round(newLeft * 10) / 10,
    });
    handled = true;
  } else if (key === "ArrowRight") {
    const newLeft = Math.max(0, Math.min(100 - w, l + posStep));
    emitZoneUpdate({
      ...curr,
      left_pct: Math.round(newLeft * 10) / 10,
    });
    handled = true;
  } else if (key === "+" || key === "=") {
    const newW = Math.max(8, Math.min(100 - l, w + sizeStep));
    const newH = Math.max(8, Math.min(100 - t, h + sizeStep));
    emitZoneUpdate({
      ...curr,
      width_pct: Math.round(newW * 10) / 10,
      height_pct: Math.round(newH * 10) / 10,
    });
    handled = true;
  } else if (key === "-" || key === "_") {
    const newW = Math.max(8, w - sizeStep);
    const newH = Math.max(8, h - sizeStep);
    emitZoneUpdate({
      ...curr,
      width_pct: Math.round(newW * 10) / 10,
      height_pct: Math.round(newH * 10) / 10,
    });
    handled = true;
  } else if (key === "[" || key === "{") {
    let newAngle = Math.round(angle - rotStep);
    while (newAngle < -180) newAngle += 360;
    emitZoneUpdate({
      ...curr,
      angle_deg: newAngle,
    });
    handled = true;
  } else if (key === "]" || key === "}") {
    let newAngle = Math.round(angle + rotStep);
    while (newAngle > 180) newAngle -= 360;
    emitZoneUpdate({
      ...curr,
      angle_deg: newAngle,
    });
    handled = true;
  } else if (key === "r" || key === "R") {
    let newAngle = Math.round(angle + (isShift ? -90 : 90));
    while (newAngle > 180) newAngle -= 360;
    while (newAngle < -180) newAngle += 360;
    emitZoneUpdate({
      ...curr,
      angle_deg: newAngle,
    });
    handled = true;
  } else if (key === "c" || key === "C") {
    const newLeft = Math.max(0, Math.min(100 - w, (100 - w) / 2));
    const newTop = Math.max(0, Math.min(100 - h, (100 - h) / 2));
    emitZoneUpdate({
      ...curr,
      left_pct: Math.round(newLeft * 10) / 10,
      top_pct: Math.round(newTop * 10) / 10,
    });
    handled = true;
  }

  if (handled) {
    e.preventDefault();
    e.stopPropagation();
  }
}

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
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

      <!-- Layer 1: Pure Blended Artworks for ALL zones -->
      <template v-if="templateImageUrl">
        <div
          v-for="(zone, idx) in activeZones"
          :key="zone.id || `zone-art-${idx}`"
          class="absolute pointer-events-none select-none"
          :style="[
            getBoxStyle(zone),
            { mixBlendMode: resolveCssBlend(zone.blend_mode) as any }
          ]"
        >
          <img
            v-if="getZoneArtworkUrl(zone)"
            :src="getZoneArtworkUrl(zone)!"
            :alt="`Artwork Zone ${idx + 1}`"
            class="w-full h-full object-contain pointer-events-none select-none block"
          >
        </div>
      </template>

      <!-- Layer 2: Interactive Controls & Multi-Zone Bounding Boxes (Edit mode only) -->
      <template v-if="templateImageUrl && viewMode === 'edit'">
        <!-- Inactive selectable zone outlines -->
        <template v-for="(zone, idx) in activeZones" :key="`inactive-zone-${idx}`">
          <div
            v-if="idx !== currentZoneIndex"
            class="absolute cursor-pointer border border-dashed border-white/70 hover:border-primary bg-white/5 hover:bg-primary/15 transition-all rounded-xs z-10 group/zone"
            :style="getBoxStyle(zone)"
            :title="`Click to select Zone ${idx + 1}`"
            @mousedown="(e) => selectZone(idx, e)"
          >
            <span class="absolute -top-5 left-1/2 -translate-x-1/2 px-1.5 py-0.2 bg-slate-900/90 text-white rounded text-[9px] font-mono border border-slate-700 pointer-events-none shadow-xs group-hover/zone:border-primary group-hover/zone:text-primary">
              Zone {{ idx + 1 }}
            </span>
          </div>
        </template>

        <!-- Active Interactive Control Box for Current Zone -->
        <div
          v-if="activeZones.length > 0"
          tabindex="0"
          role="region"
          aria-label="Artwork Placement Controls"
          class="absolute cursor-move border-2 border-dashed border-primary bg-primary/10 shadow-sm select-none z-20 focus:outline-none focus:ring-2 focus:ring-primary focus:border-solid transition-shadow"
          :style="getBoxStyle(currentZone)"
          @mousedown="startDrag"
          @keydown="handleKeyDown"
        >
          <!-- Top Rotation Stalk & Handle -->
          <div class="absolute -top-7 left-1/2 -translate-x-1/2 flex flex-col items-center pointer-events-auto select-none">
            <div
              class="size-5 rounded-full bg-primary text-white border-2 border-white shadow-md flex items-center justify-center cursor-grab active:cursor-grabbing hover:scale-125 transition-transform"
              title="Drag to rotate artwork"
              @pointerdown="startRotate"
              @mousedown.stop
            >
              <Icon name="lucide:rotate-cw" class="size-2.5 text-white" aria-hidden="true" />
            </div>
            <div class="w-0.5 h-2 bg-primary/70" />
          </div>

          <!-- Zone Tag & Live Measurement Pill -->
          <div
            class="absolute -top-12 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-slate-900/90 text-white rounded-md text-[9px] font-mono whitespace-nowrap pointer-events-none shadow-md border border-slate-700/60 flex items-center gap-1.5"
          >
            <span v-if="activeZones.length > 1" class="text-primary font-bold">Z{{ currentZoneIndex + 1 }}</span>
            <span>{{ Math.round(getZoneLeftPct(currentZone)) }}%, {{ Math.round(getZoneTopPct(currentZone)) }}%</span>
            <span>·</span>
            <span>{{ Math.round(getZoneWidthPct(currentZone)) }}×{{ Math.round(getZoneHeightPct(currentZone)) }}%</span>
            <span v-if="currentZone.angle_deg">· {{ currentZone.angle_deg }}°</span>
          </div>

          <!-- Resize Handle in Bottom Right -->
          <div
            class="absolute -bottom-2 -right-2 h-5 w-5 bg-primary border-2 border-white rounded-full cursor-nwse-resize shadow-md flex items-center justify-center hover:scale-125 transition-transform"
            title="Drag to resize artwork bounding box"
            @mousedown="startResize"
          >
            <div class="h-1.5 w-1.5 bg-white rounded-full" />
          </div>

          <!-- Center Crosshair for Active Zone -->
          <div class="absolute inset-0 pointer-events-none flex items-center justify-center opacity-40">
            <div class="w-2 h-0.5 bg-primary absolute" />
            <div class="h-2 w-0.5 bg-primary absolute" />
          </div>
        </div>
      </template>

      <!-- Keyboard Nudge Navigation Pill -->
      <div
        v-if="templateImageUrl && viewMode === 'edit'"
        class="absolute bottom-2.5 left-2.5 z-30 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/80 text-zinc-300 text-[10px] font-mono backdrop-blur-xs border border-white/10 shadow-xs pointer-events-none select-none transition-opacity"
      >
        <Icon name="lucide:keyboard" class="size-3 text-primary shrink-0" aria-hidden="true" />
        <span>Arrow keys to move <span class="text-zinc-500 hidden sm:inline">(Shift: 5% · Alt: 0.2%)</span></span>
      </div>
    </div>
  </div>
</template>
