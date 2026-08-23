<script setup lang="ts">
import { ref } from "vue";
import Badge from "~/components/ui/Badge.vue";
import Skeleton from "~/components/ui/Skeleton.vue";
import { sanitizeUrl } from "~/utils/sanitize";

defineProps<{
  masterImageUrl: string | null;
  outputAssetId?: string | null;
  renderNonce: number;
}>();

const isZoomed = ref(false);
const isCopied = ref(false);

async function copyUrl(url: string | null) {
  if (!url || typeof navigator === "undefined" || !navigator.clipboard) return;
  try {
    await navigator.clipboard.writeText(url);
    isCopied.value = true;
    setTimeout(() => {
      isCopied.value = false;
    }, 2000);
  } catch {
    // Non-blocking fallback
  }
}
</script>

<template>
  <div class="border border-border rounded-2xl p-4 bg-card text-card-foreground shadow-xs space-y-3.5 hover:shadow-md transition-all duration-200">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-start sm:items-center gap-2.5 min-w-0">
        <div class="size-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center border border-emerald-500/30 shadow-2xs shrink-0 mt-0.5 sm:mt-0">
          <Icon name="lucide:file-check" class="size-4 shrink-0" aria-hidden="true" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5 flex-wrap">
            <h5 class="text-xs font-bold text-foreground leading-tight">Master Print File</h5>
            <span class="inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-md border border-emerald-500/30 shrink-0">
              <span class="size-1 rounded-full bg-emerald-500 animate-pulse" />
              Master PNG
            </span>
          </div>
          <p class="text-[10px] text-muted-foreground font-medium truncate">300 DPI Transparent Print Graphic</p>
        </div>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <Badge variant="outline" class="text-[10px] px-2 py-0.5 font-bold bg-slate-50 text-foreground border-border shadow-2xs font-mono">
          4500 × 5400 px
        </Badge>
      </div>
    </div>

    <!-- Checkerboard Canvas Preview Area -->
    <div class="relative group w-full h-[280px] rounded-xl overflow-hidden border border-border/80 bg-[linear-gradient(45deg,#F1F5F9_25%,transparent_25%),linear-gradient(-45deg,#F1F5F9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#F1F5F9_75%),linear-gradient(-45deg,transparent_75%,#F1F5F9_75%)] bg-[size:16px_16px] bg-[position:0_0,0_8px,8px_-8px,-8px_0px] shadow-inner flex items-center justify-center">
      <!-- Master Image -->
      <img
        v-if="masterImageUrl"
        :key="masterImageUrl + '_' + (outputAssetId || '') + '_' + renderNonce"
        :src="masterImageUrl"
        alt="Master Production PNG"
        class="object-contain w-full h-full max-h-[280px] p-3 transition-transform duration-300 ease-out group-hover:scale-105"
      >
      <div v-else class="w-full h-full p-6 flex flex-col items-center justify-center gap-3">
        <Skeleton class="w-3/4 h-3/4 rounded-xl" />
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <Icon name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
          <span>Generating master PNG...</span>
        </div>
      </div>

      <!-- Quick Action Overlay on Hover -->
      <div
        v-if="masterImageUrl"
        class="absolute inset-0 bg-black/40 backdrop-blur-2xs opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-2"
      >
        <button
          type="button"
          class="h-8 px-3 rounded-lg bg-white/95 hover:bg-white text-slate-900 text-xs font-semibold shadow-md flex items-center gap-1.5 cursor-pointer active:scale-95 transition-all"
          title="Inspect High-Res Zoom"
          @click="isZoomed = true"
        >
          <Icon name="lucide:zoom-in" class="size-3.5" aria-hidden="true" />
          <span>Zoom</span>
        </button>

        <button
          type="button"
          class="h-8 w-8 rounded-lg bg-white/95 hover:bg-white text-slate-900 flex items-center justify-center shadow-md cursor-pointer active:scale-95 transition-all"
          :title="isCopied ? 'Copied!' : 'Copy Asset Link'"
          @click="copyUrl(masterImageUrl)"
        >
          <Icon :name="isCopied ? 'lucide:check' : 'lucide:copy'" class="size-3.5" :class="{ 'text-emerald-600': isCopied }" aria-hidden="true" />
        </button>

        <a
          :href="sanitizeUrl(masterImageUrl)"
          target="_blank"
          rel="noopener noreferrer"
          class="h-8 w-8 rounded-lg bg-white/95 hover:bg-white text-slate-900 flex items-center justify-center shadow-md cursor-pointer active:scale-95 transition-all"
          title="Open in new tab"
        >
          <Icon name="lucide:external-link" class="size-3.5" aria-hidden="true" />
        </a>
      </div>
    </div>

    <!-- Footer Toolbar & Specs -->
    <div class="flex items-center justify-between pt-2 border-t border-border/80 text-xs">
      <div class="flex items-center gap-2 text-muted-foreground">
        <span class="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200/50">
          <span class="size-1.5 rounded-full bg-emerald-500 inline-block" />
          Ready for print
        </span>
        <span class="text-[10px] text-muted-foreground hidden sm:inline-block">• 5:6 Ratio</span>
      </div>

      <a
        v-if="masterImageUrl"
        :href="sanitizeUrl(masterImageUrl)"
        target="_blank"
        rel="noopener noreferrer"
        download="master_transparent_300dpi.png"
        class="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 active:bg-black text-white px-3.5 py-1.5 text-xs font-semibold shadow-xs hover:shadow-sm active:scale-95 transition-all duration-150 cursor-pointer"
      >
        <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
        <span>Download Master PNG</span>
      </a>
    </div>

    <!-- High-Resolution Inspection Zoom Modal -->
    <div
      v-if="isZoomed && masterImageUrl"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-in fade-in duration-150"
      @click="isZoomed = false"
    >
      <div class="relative max-w-4xl max-h-[90vh] bg-slate-950 rounded-2xl overflow-hidden shadow-2xl p-3 border border-slate-800 flex flex-col" @click.stop>
        <!-- Modal Top Bar -->
        <div class="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 px-2 text-slate-200">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-white">Master PNG Inspection</span>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">4500 × 5400 px @ 300 DPI</span>
          </div>
          <button
            type="button"
            class="h-7 w-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition-colors cursor-pointer"
            @click="isZoomed = false"
          >
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Image Container with Checkerboard -->
        <div class="overflow-auto max-h-[75vh] flex items-center justify-center rounded-xl bg-[linear-gradient(45deg,#1e293b_25%,transparent_25%),linear-gradient(-45deg,#1e293b_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#1e293b_75%),linear-gradient(-45deg,transparent_75%,#1e293b_75%)] bg-[size:20px_20px] bg-[position:0_0,0_10px,10px_-10px,-10px_0px] p-4">
          <img
            :src="masterImageUrl"
            alt="Master Print Fullscreen Inspection"
            class="max-h-[70vh] object-contain drop-shadow-2xl"
          >
        </div>
      </div>
    </div>
  </div>
</template>
