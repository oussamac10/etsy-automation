<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import Button from "~/components/ui/Button.vue";

const props = withDefaults(
  defineProps<{
    imageUrl: string | null;
    fileName?: string;
    defaultAspect?: number | "freeform"; // 0.8 for 4:5, 1 for 1:1, 1.5 for 3:2, or 'freeform'
  }>(),
  {
    defaultAspect: 0.8,
    fileName: "mockup_photo.jpg",
  }
);

const emit = defineEmits<{
  (e: "cancel"): void;
  (
    e: "crop",
    result: {
      croppedBlob: Blob;
      croppedFile: File;
      croppedUrl: string;
      width: number;
      height: number;
    }
  ): void;
}>();

// Aspect presets
type AspectMode = "4:5" | "1:1" | "3:2" | "freeform";
const selectedAspect = ref<AspectMode>("4:5");

const containerRef = ref<HTMLDivElement | null>(null);
const imageRef = ref<HTMLImageElement | null>(null);
const imageNaturalWidth = ref(1000);
const imageNaturalHeight = ref(1000);
const rotationDeg = ref(0);
const isProcessingCrop = ref(false);

// Crop rectangle in percentages (0 to 100)
const cropLeft = ref(10);
const cropTop = ref(10);
const cropWidth = ref(80);
const cropHeight = ref(80);

// Drag & Resize state
const isDragging = ref(false);
const activeHandle = ref<string | null>(null);
let startMouseX = 0;
let startMouseY = 0;
let initLeft = 10;
let initTop = 10;
let initWidth = 80;
let initHeight = 80;

const targetAspectRatio = computed<number | null>(() => {
  if (selectedAspect.value === "4:5") return 4 / 5; // 0.8
  if (selectedAspect.value === "1:1") return 1.0;
  if (selectedAspect.value === "3:2") return 3 / 2; // 1.5
  return null;
});

function initCropBox(): void {
  const imgAspect = imageNaturalWidth.value / (imageNaturalHeight.value || 1);
  const targetAspect = targetAspectRatio.value;

  if (!targetAspect) {
    // Freeform: default to 85% centered
    cropLeft.value = 7.5;
    cropTop.value = 7.5;
    cropWidth.value = 85;
    cropHeight.value = 85;
    return;
  }

  const ratio = imgAspect / targetAspect;

  if (ratio >= 1.0) {
    // Image is wider than target aspect: constrain by height
    const h = 85;
    const w = Math.min(95, h / ratio);
    cropWidth.value = Math.round(w * 10) / 10;
    cropHeight.value = h;
    cropLeft.value = Math.round(((100 - cropWidth.value) / 2) * 10) / 10;
    cropTop.value = Math.round(((100 - cropHeight.value) / 2) * 10) / 10;
  } else {
    // Image is taller than target aspect: constrain by width
    const w = 85;
    const h = Math.min(95, w * ratio);
    cropWidth.value = w;
    cropHeight.value = Math.round(h * 10) / 10;
    cropLeft.value = Math.round(((100 - cropWidth.value) / 2) * 10) / 10;
    cropTop.value = Math.round(((100 - cropHeight.value) / 2) * 10) / 10;
  }
}

function handleAspectChange(mode: AspectMode): void {
  selectedAspect.value = mode;
  initCropBox();
}

function rotateClockwise(): void {
  rotationDeg.value = (rotationDeg.value + 90) % 360;
  const temp = imageNaturalWidth.value;
  imageNaturalWidth.value = imageNaturalHeight.value;
  imageNaturalHeight.value = temp;
  initCropBox();
}

function onImageLoad(e: Event): void {
  const img = e.target as HTMLImageElement;
  if (img.naturalWidth && img.naturalHeight) {
    imageNaturalWidth.value = img.naturalWidth;
    imageNaturalHeight.value = img.naturalHeight;
    initCropBox();
  }
}

watch(
  () => props.imageUrl,
  (newUrl) => {
    if (newUrl) {
      rotationDeg.value = 0;
      if (props.defaultAspect === "freeform") {
        selectedAspect.value = "freeform";
      } else if (props.defaultAspect === 1) {
        selectedAspect.value = "1:1";
      } else if (props.defaultAspect === 1.5) {
        selectedAspect.value = "3:2";
      } else {
        selectedAspect.value = "4:5";
      }

      const test = new Image();
      test.onload = () => {
        imageNaturalWidth.value = test.naturalWidth;
        imageNaturalHeight.value = test.naturalHeight;
        initCropBox();
      };
      test.src = newUrl;
    }
  },
  { immediate: true }
);

// Drag Handler for Moving Crop Box
function startMoveDrag(e: MouseEvent): void {
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = true;
  activeHandle.value = null;
  startMouseX = e.clientX;
  startMouseY = e.clientY;
  initLeft = cropLeft.value;
  initTop = cropTop.value;

  window.addEventListener("mousemove", onPointerMove);
  window.addEventListener("mouseup", onPointerUp);
}

// Resize Handler for Handles
function startResizeDrag(handle: string, e: MouseEvent): void {
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = true;
  activeHandle.value = handle;
  startMouseX = e.clientX;
  startMouseY = e.clientY;
  initLeft = cropLeft.value;
  initTop = cropTop.value;
  initWidth = cropWidth.value;
  initHeight = cropHeight.value;

  window.addEventListener("mousemove", onPointerMove);
  window.addEventListener("mouseup", onPointerUp);
}

function onPointerMove(e: MouseEvent): void {
  if (!isDragging.value || !containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  const dxPct = ((e.clientX - startMouseX) / rect.width) * 100;
  const dyPct = ((e.clientY - startMouseY) / rect.height) * 100;

  if (activeHandle.value === null) {
    // Panning/Moving Box
    const newL = Math.max(0, Math.min(100 - cropWidth.value, initLeft + dxPct));
    const newT = Math.max(0, Math.min(100 - cropHeight.value, initTop + dyPct));
    cropLeft.value = Math.round(newL * 10) / 10;
    cropTop.value = Math.round(newT * 10) / 10;
    return;
  }

  const handle = activeHandle.value;
  const imgAspect = imageNaturalWidth.value / (imageNaturalHeight.value || 1);
  const targetAspect = targetAspectRatio.value;

  if (!targetAspect) {
    // Freeform Resizing
    if (handle.includes("e")) {
      cropWidth.value = Math.max(10, Math.min(100 - cropLeft.value, initWidth + dxPct));
    }
    if (handle.includes("s")) {
      cropHeight.value = Math.max(10, Math.min(100 - cropTop.value, initHeight + dyPct));
    }
    if (handle.includes("w")) {
      const deltaW = Math.min(initWidth - 10, dxPct);
      const newL = Math.max(0, initLeft + deltaW);
      cropWidth.value = initWidth + (initLeft - newL);
      cropLeft.value = newL;
    }
    if (handle.includes("n")) {
      const deltaH = Math.min(initHeight - 10, dyPct);
      const newT = Math.max(0, initTop + deltaH);
      cropHeight.value = initHeight + (initTop - newT);
      cropTop.value = newT;
    }
  } else {
    // Aspect Ratio Locked Resizing
    const aspectFactor = imgAspect / targetAspect;
    let delta = 0;

    if (handle === "se") {
      delta = (dxPct + dyPct / aspectFactor) / 2;
      const newW = Math.max(15, Math.min(100 - initLeft, initWidth + delta));
      const newH = newW * aspectFactor;
      if (initTop + newH <= 100) {
        cropWidth.value = Math.round(newW * 10) / 10;
        cropHeight.value = Math.round(newH * 10) / 10;
      }
    } else if (handle === "nw") {
      delta = (dxPct + dyPct / aspectFactor) / 2;
      const newW = Math.max(15, initWidth - delta);
      const newH = newW * aspectFactor;
      const newL = initLeft + (initWidth - newW);
      const newT = initTop + (initHeight - newH);
      if (newL >= 0 && newT >= 0) {
        cropWidth.value = Math.round(newW * 10) / 10;
        cropHeight.value = Math.round(newH * 10) / 10;
        cropLeft.value = Math.round(newL * 10) / 10;
        cropTop.value = Math.round(newT * 10) / 10;
      }
    } else if (handle === "ne") {
      delta = (dxPct - dyPct / aspectFactor) / 2;
      const newW = Math.max(15, Math.min(100 - initLeft, initWidth + delta));
      const newH = newW * aspectFactor;
      const newT = initTop + (initHeight - newH);
      if (newT >= 0) {
        cropWidth.value = Math.round(newW * 10) / 10;
        cropHeight.value = Math.round(newH * 10) / 10;
        cropTop.value = Math.round(newT * 10) / 10;
      }
    } else if (handle === "sw") {
      delta = (-dxPct + dyPct / aspectFactor) / 2;
      const newW = Math.max(15, initWidth + delta);
      const newH = newW * aspectFactor;
      const newL = initLeft + (initWidth - newW);
      if (newL >= 0 && initTop + newH <= 100) {
        cropWidth.value = Math.round(newW * 10) / 10;
        cropHeight.value = Math.round(newH * 10) / 10;
        cropLeft.value = Math.round(newL * 10) / 10;
      }
    }
  }
}

function onPointerUp(): void {
  isDragging.value = false;
  activeHandle.value = null;
  window.removeEventListener("mousemove", onPointerMove);
  window.removeEventListener("mouseup", onPointerUp);
}

onUnmounted(() => {
  window.removeEventListener("mousemove", onPointerMove);
  window.removeEventListener("mouseup", onPointerUp);
});

// Crop Execution via HTML5 Canvas
async function applyCrop(): Promise<void> {
  if (!props.imageUrl) return;
  isProcessingCrop.value = true;

  try {
    const srcImg = new Image();
    srcImg.crossOrigin = "anonymous";

    await new Promise<void>((resolve, reject) => {
      srcImg.onload = () => resolve();
      srcImg.onerror = (err) => reject(err);
      srcImg.src = props.imageUrl!;
    });

    const origW = srcImg.naturalWidth;
    const origH = srcImg.naturalHeight;

    let baseCanvas = document.createElement("canvas");
    let baseCtx = baseCanvas.getContext("2d")!;

    if (rotationDeg.value === 90 || rotationDeg.value === 270) {
      baseCanvas.width = origH;
      baseCanvas.height = origW;
    } else {
      baseCanvas.width = origW;
      baseCanvas.height = origH;
    }

    baseCtx.save();
    baseCtx.translate(baseCanvas.width / 2, baseCanvas.height / 2);
    baseCtx.rotate((rotationDeg.value * Math.PI) / 180);
    baseCtx.drawImage(srcImg, -origW / 2, -origH / 2);
    baseCtx.restore();

    const sx = Math.round((cropLeft.value / 100) * baseCanvas.width);
    const sy = Math.round((cropTop.value / 100) * baseCanvas.height);
    const sw = Math.round((cropWidth.value / 100) * baseCanvas.width);
    const sh = Math.round((cropHeight.value / 100) * baseCanvas.height);

    const outCanvas = document.createElement("canvas");
    outCanvas.width = Math.max(1, sw);
    outCanvas.height = Math.max(1, sh);
    const outCtx = outCanvas.getContext("2d")!;
    outCtx.imageSmoothingEnabled = true;
    outCtx.imageSmoothingQuality = "high";

    outCtx.drawImage(baseCanvas, sx, sy, sw, sh, 0, 0, outCanvas.width, outCanvas.height);

    const blob = await new Promise<Blob>((resolve, reject) => {
      outCanvas.toBlob(
        (b) => {
          if (b) resolve(b);
          else reject(new Error("Canvas toBlob failed"));
        },
        "image/jpeg",
        0.95
      );
    });

    const croppedUrl = URL.createObjectURL(blob);
    const cleanFileName = (props.fileName || "cropped_mockup.jpg").replace(/\.[^/.]+$/, "") + ".jpg";
    const croppedFile = new File([blob], cleanFileName, { type: "image/jpeg" });

    emit("crop", {
      croppedBlob: blob,
      croppedFile,
      croppedUrl,
      width: outCanvas.width,
      height: outCanvas.height,
    });
  } catch (err) {
    console.error("Failed to crop image:", err);
  } finally {
    isProcessingCrop.value = false;
  }
}
</script>

<template>
  <div class="space-y-4 select-none">
    <!-- Aspect Ratio Toolbar & Quick Actions -->
    <div class="flex flex-wrap items-center justify-between gap-2 p-2 rounded-xl bg-secondary/60 border border-border">
      <div class="flex items-center gap-1.5 flex-wrap">
        <span class="text-xs font-bold text-foreground mr-1 flex items-center gap-1">
          <Icon name="lucide:crop" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Crop Frame:</span>
        </span>

        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer inline-flex items-center gap-1"
          :class="selectedAspect === '4:5' ? 'bg-primary text-white shadow-2xs' : 'bg-white text-secondary-foreground border border-border hover:bg-secondary hover:text-foreground'"
          @click="handleAspectChange('4:5')"
        >
          <span>4:5</span>
          <span class="text-[10px] opacity-80">(Etsy)</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer inline-flex items-center gap-1"
          :class="selectedAspect === '1:1' ? 'bg-primary text-white shadow-2xs' : 'bg-white text-secondary-foreground border border-border hover:bg-secondary hover:text-foreground'"
          @click="handleAspectChange('1:1')"
        >
          <span>1:1</span>
          <span class="text-[10px] opacity-80">(Square)</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer inline-flex items-center gap-1"
          :class="selectedAspect === '3:2' ? 'bg-primary text-white shadow-2xs' : 'bg-white text-secondary-foreground border border-border hover:bg-secondary hover:text-foreground'"
          @click="handleAspectChange('3:2')"
        >
          <span>3:2</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer inline-flex items-center gap-1"
          :class="selectedAspect === 'freeform' ? 'bg-primary text-white shadow-2xs' : 'bg-white text-secondary-foreground border border-border hover:bg-secondary hover:text-foreground'"
          @click="handleAspectChange('freeform')"
        >
          <Icon name="lucide:scan" class="size-3" aria-hidden="true" />
          <span>Freeform</span>
        </button>
      </div>

      <div class="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          class="text-xs h-7 px-2 cursor-pointer inline-flex items-center gap-1 text-secondary-foreground bg-white"
          title="Rotate photo 90 degrees"
          @click="rotateClockwise"
        >
          <Icon name="lucide:rotate-cw" class="size-3" aria-hidden="true" />
          <span>Rotate 90°</span>
        </Button>

        <Button
          variant="outline"
          size="sm"
          class="text-xs h-7 px-2 cursor-pointer inline-flex items-center gap-1 text-secondary-foreground bg-white"
          title="Reset crop frame to full image"
          @click="initCropBox"
        >
          <Icon name="lucide:maximize-2" class="size-3" aria-hidden="true" />
          <span>Reset</span>
        </Button>
      </div>
    </div>

    <!-- Main Cropper Viewport Frame -->
    <div class="relative w-full max-h-[380px] bg-zinc-950 rounded-2xl overflow-hidden shadow-inner flex items-center justify-center p-3">
      <div
        ref="containerRef"
        class="relative max-h-[360px] max-w-full rounded-xl overflow-hidden shadow-2xl flex items-center justify-center"
        :style="{
          aspectRatio: `${imageNaturalWidth} / ${imageNaturalHeight}`,
        }"
      >
        <!-- Base Image -->
        <img
          v-if="imageUrl"
          ref="imageRef"
          :src="imageUrl"
          alt="Source Mockup"
          class="w-full h-full object-contain pointer-events-none block"
          :style="{
            transform: `rotate(${rotationDeg}deg)`,
          }"
          @load="onImageLoad"
        >

        <!-- Dimmed Dark Mask Outside Crop Box -->
        <div class="absolute inset-x-0 top-0 bg-black/65 pointer-events-none transition-all" :style="{ height: `${cropTop}%` }" />
        <div class="absolute inset-x-0 bottom-0 bg-black/65 pointer-events-none transition-all" :style="{ height: `${100 - (cropTop + cropHeight)}%` }" />
        <div class="absolute bg-black/65 pointer-events-none transition-all" :style="{ top: `${cropTop}%`, bottom: `${100 - (cropTop + cropHeight)}%`, left: 0, width: `${cropLeft}%` }" />
        <div class="absolute bg-black/65 pointer-events-none transition-all" :style="{ top: `${cropTop}%`, bottom: `${100 - (cropTop + cropHeight)}%`, right: 0, width: `${100 - (cropLeft + cropWidth)}%` }" />

        <!-- Interactive Bounding Crop Box -->
        <div
          class="absolute border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.5),0_0_20px_rgba(0,0,0,0.5)] cursor-move select-none"
          :style="{
            left: `${cropLeft}%`,
            top: `${cropTop}%`,
            width: `${cropWidth}%`,
            height: `${cropHeight}%`,
          }"
          @mousedown="startMoveDrag"
        >
          <!-- Rule-of-Thirds Grid Lines -->
          <div class="absolute inset-0 pointer-events-none grid grid-cols-3 grid-rows-3 opacity-40">
            <div class="border-r border-b border-white/60" />
            <div class="border-r border-b border-white/60" />
            <div class="border-b border-white/60" />
            <div class="border-r border-b border-white/60" />
            <div class="border-r border-b border-white/60" />
            <div class="border-b border-white/60" />
            <div class="border-r border-b border-white/60" />
            <div class="border-r border-b border-white/60" />
            <div />
          </div>

          <!-- Corner Resize Handles (NW, NE, SW, SE) -->
          <div
            class="absolute -top-2 -left-2 size-4 bg-white border-2 border-primary rounded-xs shadow-md cursor-nwse-resize hover:scale-125 transition-transform"
            @mousedown="(e) => startResizeDrag('nw', e)"
          />
          <div
            class="absolute -top-2 -right-2 size-4 bg-white border-2 border-primary rounded-xs shadow-md cursor-nesw-resize hover:scale-125 transition-transform"
            @mousedown="(e) => startResizeDrag('ne', e)"
          />
          <div
            class="absolute -bottom-2 -left-2 size-4 bg-white border-2 border-primary rounded-xs shadow-md cursor-nesw-resize hover:scale-125 transition-transform"
            @mousedown="(e) => startResizeDrag('sw', e)"
          />
          <div
            class="absolute -bottom-2 -right-2 size-4 bg-white border-2 border-primary rounded-xs shadow-md cursor-nwse-resize hover:scale-125 transition-transform"
            @mousedown="(e) => startResizeDrag('se', e)"
          />
        </div>
      </div>
    </div>

    <!-- Bottom Actions Bar inside the view -->
    <div class="flex items-center justify-between pt-1">
      <p class="text-[11px] text-muted-foreground">
        💡 Drag the frame to center your product · Drag corners to resize
      </p>

      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          class="text-xs cursor-pointer"
          :disabled="isProcessingCrop"
          @click="emit('cancel')"
        >
          Cancel
        </Button>

        <Button
          variant="default"
          size="sm"
          class="bg-primary hover:bg-primary-hover text-white font-bold gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
          :disabled="isProcessingCrop"
          @click="applyCrop"
        >
          <Icon v-if="isProcessingCrop" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
          <span>{{ isProcessingCrop ? "Cropping..." : "Apply & Continue" }}</span>
        </Button>
      </div>
    </div>
  </div>
</template>
