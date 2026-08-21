<script setup lang="ts">
import { computed } from "vue";
import { BLEND_MODE_OPTIONS, getBlendModeInfo } from "~/utils/mockupProducts";
import type { MockupBlendMode } from "~/types/mockup";

const props = defineProps<{
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  angleDeg: number;
  blendMode: MockupBlendMode | string;
  templateName: string;
  saveToLibrary: boolean;
  isCover: boolean;
  isCompositing: boolean;
  isUploadingNew: boolean;
}>();

const emit = defineEmits<{
  (e: "update:leftPct", val: number): void;
  (e: "update:topPct", val: number): void;
  (e: "update:widthPct", val: number): void;
  (e: "update:heightPct", val: number): void;
  (e: "update:angleDeg", val: number): void;
  (e: "update:blendMode", val: MockupBlendMode | string): void;
  (e: "update:templateName", val: string): void;
  (e: "update:saveToLibrary", val: boolean): void;
  (e: "update:isCover", val: boolean): void;
  (e: "resetPreset"): void;
  (e: "centerHorizontal"): void;
  (e: "centerBoth"): void;
}>();

const activeBlendInfo = computed(() => getBlendModeInfo(props.blendMode));

function rotateLeft(): void {
  let a = (props.angleDeg || 0) - 90;
  while (a < -180) a += 360;
  emit("update:angleDeg", a);
}

function rotateRight(): void {
  let a = (props.angleDeg || 0) + 90;
  while (a > 180) a -= 360;
  emit("update:angleDeg", a);
}

function setAngle(deg: number): void {
  emit("update:angleDeg", deg);
}
</script>

<template>
  <div class="space-y-4">
    <!-- Quick Alignment & Reset Toolbar -->
    <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-border">
      <span class="text-xs font-bold text-foreground flex items-center gap-1.5 shrink-0">
        <Icon name="lucide:sliders" class="size-3.5 text-primary" aria-hidden="true" />
        <span>Placement Settings</span>
      </span>

      <div class="flex items-center gap-1.5 flex-wrap">
        <div class="flex items-center gap-1 bg-secondary/60 p-0.5 rounded-lg border border-border shrink-0">
          <button
            type="button"
            class="px-2.5 py-1 rounded-md text-[11px] font-bold text-secondary-foreground hover:text-primary hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
            title="Center artwork horizontally & vertically"
            @click="emit('centerBoth')"
          >
            <Icon name="lucide:crosshair" class="size-3 text-primary shrink-0" aria-hidden="true" />
            <span class="whitespace-nowrap">Center All</span>
          </button>

          <button
            type="button"
            class="px-2.5 py-1 rounded-md text-[11px] font-bold text-secondary-foreground hover:text-primary hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
            title="Center artwork horizontally"
            @click="emit('centerHorizontal')"
          >
            <Icon name="lucide:align-horizontal-justify-center" class="size-3 text-primary shrink-0" aria-hidden="true" />
            <span class="whitespace-nowrap">Center X</span>
          </button>

          <button
            type="button"
            class="px-2 py-1 rounded-md text-[11px] font-bold text-muted-foreground hover:text-foreground hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
            title="Reset to default preset"
            @click="emit('resetPreset')"
          >
            <Icon name="lucide:rotate-ccw" class="size-3 text-muted-foreground shrink-0" aria-hidden="true" />
            <span class="whitespace-nowrap">Reset</span>
          </button>
        </div>

        <!-- Quick Rotate Toolbar -->
        <div class="flex items-center gap-1 bg-secondary/60 p-0.5 rounded-lg border border-border shrink-0">
          <button
            type="button"
            class="px-2 py-1 rounded-md text-[11px] font-bold text-secondary-foreground hover:text-primary hover:bg-white transition-all cursor-pointer inline-flex items-center gap-0.5 shadow-2xs hover:shadow-xs"
            title="Rotate 90 degrees counter-clockwise"
            @click="rotateLeft"
          >
            <Icon name="lucide:rotate-ccw" class="size-3 text-primary shrink-0" aria-hidden="true" />
            <span>-90°</span>
          </button>

          <button
            type="button"
            class="px-2 py-1 rounded-md text-[11px] font-bold text-secondary-foreground hover:text-primary hover:bg-white transition-all cursor-pointer inline-flex items-center gap-0.5 shadow-2xs hover:shadow-xs"
            title="Rotate 90 degrees clockwise"
            @click="rotateRight"
          >
            <Icon name="lucide:rotate-cw" class="size-3 text-primary shrink-0" aria-hidden="true" />
            <span>+90°</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Sliders Grid -->
    <div class="grid grid-cols-2 gap-3 text-xs">
      <!-- Scale (Width) -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-secondary-foreground">
          <span class="font-medium">Width Scale</span>
          <span class="font-mono text-foreground font-bold">{{ Math.round(widthPct) }}%</span>
        </div>
        <input
          type="range"
          min="10"
          max="95"
          :value="widthPct"
          class="w-full accent-primary cursor-pointer"
          @input="(e) => emit('update:widthPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Height Scale -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-secondary-foreground">
          <span class="font-medium">Height Scale</span>
          <span class="font-mono text-foreground font-bold">{{ Math.round(heightPct) }}%</span>
        </div>
        <input
          type="range"
          min="10"
          max="95"
          :value="heightPct"
          class="w-full accent-primary cursor-pointer"
          @input="(e) => emit('update:heightPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Left Position -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-secondary-foreground">
          <span class="font-medium">Horizontal (X)</span>
          <span class="font-mono text-foreground font-bold">{{ Math.round(leftPct) }}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="90"
          :value="leftPct"
          class="w-full accent-primary cursor-pointer"
          @input="(e) => emit('update:leftPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Top Position -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-secondary-foreground">
          <span class="font-medium">Vertical (Y)</span>
          <span class="font-mono text-foreground font-bold">{{ Math.round(topPct) }}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="90"
          :value="topPct"
          class="w-full accent-primary cursor-pointer"
          @input="(e) => emit('update:topPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Rotation -->
      <div class="space-y-1.5 col-span-2 pt-1 border-t border-border/60">
        <div class="flex items-center justify-between text-secondary-foreground">
          <span class="font-semibold flex items-center gap-1.5">
            <Icon name="lucide:rotate-cw" class="size-3 text-primary" aria-hidden="true" />
            <span>Rotation Angle</span>
          </span>
          <span class="font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md border border-primary/20 text-[11px]">
            {{ angleDeg }}°
          </span>
        </div>
        <input
          type="range"
          min="-180"
          max="180"
          step="1"
          :value="angleDeg"
          class="w-full accent-primary cursor-pointer"
          @input="(e) => emit('update:angleDeg', Number((e.target as HTMLInputElement).value))"
        >
        <!-- Quick Angle Buttons -->
        <div class="flex items-center justify-between gap-1 pt-0.5">
          <button
            v-for="deg in [-90, -45, 0, 45, 90]"
            :key="deg"
            type="button"
            class="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold transition-all cursor-pointer"
            :class="angleDeg === deg ? 'bg-primary text-white shadow-2xs font-bold' : 'bg-secondary/60 text-secondary-foreground hover:text-foreground hover:bg-secondary border border-border'"
            @click="setAngle(deg)"
          >
            {{ deg > 0 ? `+${deg}°` : `${deg}°` }}
          </button>
        </div>
      </div>
    </div>

    <!-- Enhanced Texture Blend Mode Section -->
    <div class="pt-3 border-t border-border space-y-2.5">
      <div class="flex items-center justify-between">
        <label class="text-xs font-bold text-foreground flex items-center gap-1.5">
          <Icon name="lucide:palette" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Texture Blend Mode</span>
        </label>
        <span class="text-[10px] font-mono text-muted-foreground uppercase font-bold tracking-wider">
          Active: {{ activeBlendInfo.shortLabel }}
        </span>
      </div>

      <!-- Blend Mode Selection Cards Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
        <button
          v-for="opt in BLEND_MODE_OPTIONS"
          :key="opt.value"
          type="button"
          class="flex flex-col text-left p-2 rounded-xl border transition-all cursor-pointer relative"
          :class="[
            blendMode === opt.value
              ? 'bg-primary/5 border-primary ring-1 ring-primary shadow-2xs'
              : 'bg-white border-border/80 hover:border-slate-300 hover:bg-slate-50/50'
          ]"
          @click="emit('update:blendMode', opt.value)"
        >
          <div class="flex items-center justify-between gap-1 w-full mb-1">
            <span class="text-[11px] font-bold truncate" :class="blendMode === opt.value ? 'text-primary font-bold' : 'text-foreground'">
              {{ opt.shortLabel }}
            </span>
            <Icon
              :name="opt.iconName"
              class="size-3 shrink-0"
              :class="blendMode === opt.value ? 'text-primary' : 'text-muted-foreground'"
              aria-hidden="true"
            />
          </div>

          <span
            class="text-[9px] font-semibold px-1 py-0.5 rounded-md inline-block max-w-full truncate mb-0.5"
            :class="[
              blendMode === opt.value
                ? 'bg-primary/15 text-primary font-bold'
                : 'bg-secondary text-secondary-foreground'
            ]"
          >
            {{ opt.badge }}
          </span>

          <span class="text-[10px] text-muted-foreground line-clamp-2 leading-tight">
            {{ opt.bestFor }}
          </span>
        </button>
      </div>

      <!-- Active Mode Detailed Explainer Banner -->
      <div class="p-2.5 bg-slate-50 border border-slate-200/80 rounded-xl text-[11px] text-slate-700 space-y-1">
        <div class="font-bold flex items-center gap-1 text-slate-900">
          <Icon :name="activeBlendInfo.iconName" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
          <span>{{ activeBlendInfo.label }}</span>
        </div>
        <p class="text-muted-foreground leading-relaxed">
          {{ activeBlendInfo.description }}
        </p>
      </div>

      <!-- Set as Cover Toggle -->
      <div class="pt-2">
        <label class="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="isCover"
            class="rounded border-border text-primary focus:ring-primary size-4 cursor-pointer"
            @change="(e) => emit('update:isCover', (e.target as HTMLInputElement).checked)"
          >
          <span class="font-semibold">Set as primary listing cover mockup</span>
        </label>
      </div>

      <!-- Save to Library (if Uploading New Photo) -->
      <div v-if="isUploadingNew" class="space-y-2 pt-2 border-t border-border">
        <label class="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="saveToLibrary"
            class="rounded border-border text-primary focus:ring-primary size-4 cursor-pointer"
            @change="(e) => emit('update:saveToLibrary', (e.target as HTMLInputElement).checked)"
          >
          <span>Save this blank photo as reusable template in my library</span>
        </label>

        <div v-if="saveToLibrary" class="space-y-1">
          <input
            type="text"
            placeholder="Template Name (e.g. Bella Canvas 3001 Flatlay)"
            :value="templateName"
            class="w-full rounded-lg border border-border px-3 py-1.5 text-xs text-foreground focus:ring-2 focus:ring-primary bg-white"
            @input="(e) => emit('update:templateName', (e.target as HTMLInputElement).value)"
          >
        </div>
      </div>
    </div>
  </div>
</template>
