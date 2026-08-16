<script setup lang="ts">
import Badge from "~/components/ui/Badge.vue";

defineProps<{
  masterImageUrl: string | null;
  outputAssetId?: string | null;
  renderNonce: number;
}>();
</script>

<template>
  <div class="border border-border rounded-xl p-4 bg-secondary/30 space-y-3 shadow-2xs">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <div class="size-6 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200 shadow-2xs">
          <Icon name="lucide:file-check" class="size-3.5" aria-hidden="true" />
        </div>
        <div>
          <h5 class="text-xs font-bold text-foreground leading-tight">Master Print File</h5>
          <p class="text-[10px] text-muted-foreground font-medium">300 DPI Transparent PNG</p>
        </div>
      </div>
      <Badge variant="outline" class="text-[10px] px-2 py-0.5 font-semibold bg-white text-secondary-foreground border-border shadow-2xs">
        4500 × 5400 px
      </Badge>
    </div>

    <!-- Checkerboard Preview for Transparency -->
    <div class="group aspect-4500/5400 max-h-[300px] mx-auto rounded-lg overflow-hidden border border-border flex items-center justify-center bg-[linear-gradient(45deg,#F1F5F9_25%,transparent_25%),linear-gradient(-45deg,#F1F5F9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#F1F5F9_75%),linear-gradient(-45deg,transparent_75%,#F1F5F9_75%)] bg-[size:16px_16px] bg-[position:0_0,0_8px,8px_-8px,-8px_0px] relative shadow-inner">
      <img
        v-if="masterImageUrl"
        :key="masterImageUrl + '_' + (outputAssetId || '') + '_' + renderNonce"
        :src="masterImageUrl"
        alt="Master Production PNG"
        class="object-contain w-full h-full max-h-[280px] p-2 transition-transform duration-200 group-hover:scale-105"
      >
      <div v-else class="text-xs text-muted-foreground">Loading master PNG...</div>
    </div>

    <!-- Sleek Compact Footer Toolbar -->
    <div class="flex items-center justify-between pt-1 border-t border-border">
      <div class="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        <span class="size-1.5 rounded-full bg-emerald-600 inline-block" />
        <span>Ready for print</span>
      </div>

      <a
        v-if="masterImageUrl"
        :href="masterImageUrl"
        target="_blank"
        download="master_transparent_300dpi.png"
        class="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 text-xs font-semibold shadow-xs hover:shadow-sm active:scale-95 transition-all duration-150 cursor-pointer"
      >
        <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
        <span>Download Master PNG</span>
      </a>
    </div>
  </div>
</template>
