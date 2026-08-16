<script setup lang="ts">
import Button from "~/components/ui/Button.vue";

defineProps<{
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  angleDeg: number;
  blendMode: "multiply" | "over" | "screen" | "overlay" | "darken" | "lighten";
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
  (e: "update:blendMode", val: "multiply" | "over" | "screen" | "overlay" | "darken" | "lighten"): void;
  (e: "update:templateName", val: string): void;
  (e: "update:saveToLibrary", val: boolean): void;
  (e: "update:isCover", val: boolean): void;
  (e: "resetPreset"): void;
  (e: "centerHorizontal"): void;
  (e: "centerBoth"): void;
}>();
</script>

<template>
  <div class="space-y-4">
    <!-- Quick Alignment & Reset Toolbar -->
    <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-zinc-100">
      <span class="text-xs font-bold text-zinc-900 flex items-center gap-1.5 shrink-0">
        <Icon name="lucide:sliders" class="size-3.5 text-indigo-600" aria-hidden="true" />
        <span>Placement Settings</span>
      </span>

      <div class="flex items-center gap-1 bg-zinc-100 p-0.5 rounded-lg border border-zinc-200/70 shrink-0">
        <button
          type="button"
          class="px-2.5 py-1 rounded-md text-[11px] font-bold text-zinc-700 hover:text-indigo-600 hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
          title="Center artwork horizontally & vertically"
          @click="emit('centerBoth')"
        >
          <Icon name="lucide:crosshair" class="size-3 text-indigo-600 shrink-0" aria-hidden="true" />
          <span class="whitespace-nowrap">Center All</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded-md text-[11px] font-bold text-zinc-700 hover:text-indigo-600 hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
          title="Center artwork horizontally"
          @click="emit('centerHorizontal')"
        >
          <Icon name="lucide:align-horizontal-justify-center" class="size-3 text-indigo-600 shrink-0" aria-hidden="true" />
          <span class="whitespace-nowrap">Center X</span>
        </button>

        <button
          type="button"
          class="px-2 py-1 rounded-md text-[11px] font-bold text-zinc-500 hover:text-zinc-900 hover:bg-white transition-all cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shadow-2xs hover:shadow-xs"
          title="Reset to default preset"
          @click="emit('resetPreset')"
        >
          <Icon name="lucide:rotate-ccw" class="size-3 text-zinc-400 shrink-0" aria-hidden="true" />
          <span class="whitespace-nowrap">Reset</span>
        </button>
      </div>
    </div>

    <!-- Sliders Grid -->
    <div class="grid grid-cols-2 gap-3 text-xs">
      <!-- Scale (Width) -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-zinc-600">
          <span class="font-medium">Width Scale</span>
          <span class="font-mono text-zinc-900 font-bold">{{ Math.round(widthPct) }}%</span>
        </div>
        <input
          type="range"
          min="10"
          max="95"
          :value="widthPct"
          class="w-full accent-indigo-600 cursor-pointer"
          @input="(e) => emit('update:widthPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Height Scale -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-zinc-600">
          <span class="font-medium">Height Scale</span>
          <span class="font-mono text-zinc-900 font-bold">{{ Math.round(heightPct) }}%</span>
        </div>
        <input
          type="range"
          min="10"
          max="95"
          :value="heightPct"
          class="w-full accent-indigo-600 cursor-pointer"
          @input="(e) => emit('update:heightPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Left Position -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-zinc-600">
          <span class="font-medium">Horizontal (X)</span>
          <span class="font-mono text-zinc-900 font-bold">{{ Math.round(leftPct) }}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="90"
          :value="leftPct"
          class="w-full accent-indigo-600 cursor-pointer"
          @input="(e) => emit('update:leftPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Top Position -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-zinc-600">
          <span class="font-medium">Vertical (Y)</span>
          <span class="font-mono text-zinc-900 font-bold">{{ Math.round(topPct) }}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="90"
          :value="topPct"
          class="w-full accent-indigo-600 cursor-pointer"
          @input="(e) => emit('update:topPct', Number((e.target as HTMLInputElement).value))"
        >
      </div>

      <!-- Rotation -->
      <div class="space-y-1 col-span-2">
        <div class="flex items-center justify-between text-zinc-600">
          <span class="font-medium">Rotation Angle</span>
          <span class="font-mono text-zinc-900 font-bold">{{ angleDeg }}°</span>
        </div>
        <input
          type="range"
          min="-45"
          max="45"
          :value="angleDeg"
          class="w-full accent-indigo-600 cursor-pointer"
          @input="(e) => emit('update:angleDeg', Number((e.target as HTMLInputElement).value))"
        >
      </div>
    </div>

    <!-- Blend Mode & Cover Checkbox -->
    <div class="pt-2 border-t border-zinc-100 space-y-3">
      <div class="flex items-center justify-between gap-4">
        <label class="text-xs font-semibold text-zinc-700">Blend Mode</label>
        <select
          :value="blendMode"
          class="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-900 font-medium focus:ring-2 focus:ring-indigo-500 cursor-pointer"
          @change="(e) => emit('update:blendMode', (e.target as HTMLSelectElement).value as any)"
        >
          <option value="multiply">Multiply (Realistic Apparel Shadow)</option>
          <option value="over">Over / Normal (Solid Mugs & Prints)</option>
          <option value="screen">Screen (Light Colors on Dark)</option>
          <option value="overlay">Overlay (Balanced Textures)</option>
        </select>
      </div>

      <!-- Set as Cover Toggle -->
      <label class="flex items-center gap-2 text-xs font-medium text-zinc-800 cursor-pointer select-none">
        <input
          type="checkbox"
          :checked="isCover"
          class="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500 size-4"
          @change="(e) => emit('update:isCover', (e.target as HTMLInputElement).checked)"
        >
        <span>Set as primary listing cover mockup</span>
      </label>

      <!-- Save to Library (if Uploading New Photo) -->
      <div v-if="isUploadingNew" class="space-y-2 pt-2 border-t border-zinc-100">
        <label class="flex items-center gap-2 text-xs font-medium text-zinc-800 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="saveToLibrary"
            class="rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500 size-4"
            @change="(e) => emit('update:saveToLibrary', (e.target as HTMLInputElement).checked)"
          >
          <span>Save this blank photo as reusable template in my library</span>
        </label>

        <div v-if="saveToLibrary" class="space-y-1">
          <input
            type="text"
            placeholder="Template Name (e.g. Bella Canvas 3001 Flatlay)"
            :value="templateName"
            class="w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-xs text-zinc-900 focus:ring-2 focus:ring-indigo-500"
            @input="(e) => emit('update:templateName', (e.target as HTMLInputElement).value)"
          >
        </div>
      </div>
    </div>
  </div>
</template>
