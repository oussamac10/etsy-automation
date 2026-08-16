<script setup lang="ts">
import type { MockupAsset } from "~/types/mockup";
import Badge from "~/components/ui/Badge.vue";

const props = defineProps<{
  asset: MockupAsset;
  index: number;
  totalInTab: number;
  productLabel: string;
  renderNonce: number;
  isActionLoading?: boolean;
}>();

const emit = defineEmits<{
  (e: "setCover", asset: MockupAsset): void;
  (e: "adjustPlacement", asset: MockupAsset): void;
  (e: "delete", asset: MockupAsset): void;
  (e: "move", asset: MockupAsset, dir: "up" | "down"): void;
  (e: "preview", asset: MockupAsset): void;
}>();
</script>

<template>
  <div class="border border-zinc-200 rounded-xl overflow-hidden bg-white shadow-2xs hover:shadow-md transition-all group flex flex-col justify-between">
    <!-- Image Header with Badges -->
    <div class="relative aspect-square bg-zinc-100 flex items-center justify-center overflow-hidden">
      <img
        v-if="asset.url"
        :key="asset.url + '_' + renderNonce"
        :src="asset.url"
        :alt="asset.provenance?.template_name || `${productLabel} Mockup ${index + 1}`"
        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 cursor-pointer"
        @click="emit('preview', asset)"
      >
      <div v-else class="text-xs text-zinc-400">Loading mockup preview...</div>

      <!-- Cover Badge -->
      <div class="absolute top-2 left-2 flex items-center gap-1 z-10">
        <Badge
          v-if="asset.provenance?.is_cover"
          variant="success"
          class="text-[10px] px-2 py-0.5 font-bold shadow-xs flex items-center gap-1 bg-emerald-600 text-white"
        >
          <Icon name="lucide:star" class="size-3 fill-current" aria-hidden="true" />
          <span>Cover Image</span>
        </Badge>
        <span
          v-else
          class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/60 text-white backdrop-blur-xs"
        >
          #{{ index + 1 }}
        </span>
      </div>

      <!-- Actions Menu Overlay on Hover -->
      <div class="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <button
          type="button"
          title="Zoom preview"
          class="h-7 w-7 rounded-lg bg-white/90 hover:bg-white text-zinc-700 shadow-xs flex items-center justify-center backdrop-blur-xs transition-colors cursor-pointer"
          @click="emit('preview', asset)"
        >
          <Icon name="lucide:maximize-2" class="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          title="Adjust placement & template"
          class="h-7 w-7 rounded-lg bg-white/90 hover:bg-white text-zinc-700 shadow-xs flex items-center justify-center backdrop-blur-xs transition-colors cursor-pointer"
          @click="emit('adjustPlacement', asset)"
        >
          <Icon name="lucide:sliders-horizontal" class="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          title="Delete this mockup"
          class="h-7 w-7 rounded-lg bg-white/90 hover:bg-rose-50 text-rose-600 shadow-xs flex items-center justify-center backdrop-blur-xs transition-colors cursor-pointer"
          :disabled="isActionLoading"
          @click="emit('delete', asset)"
        >
          <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>

    <!-- Details Footer -->
    <div class="p-3 border-t border-zinc-100 bg-white space-y-2">
      <div class="flex items-center justify-between gap-1">
        <div class="truncate">
          <h5 class="text-xs font-bold text-zinc-900 truncate" :title="asset.provenance?.template_name">
            {{ asset.provenance?.template_name || `${productLabel} Mockup ${index + 1}` }}
          </h5>
          <p class="text-[10px] text-zinc-400 font-mono">
            {{ asset.provenance?.template_id ? 'Template Library' : 'One-off Upload' }}
          </p>
        </div>
      </div>

      <!-- Cover & Order Controls -->
      <div class="flex items-center justify-between pt-1 border-t border-zinc-50 text-xs">
        <button
          type="button"
          class="text-[11px] font-semibold flex items-center gap-1 transition-colors cursor-pointer"
          :class="asset.provenance?.is_cover ? 'text-emerald-700 font-bold' : 'text-zinc-500 hover:text-zinc-900'"
          :disabled="asset.provenance?.is_cover || isActionLoading"
          @click="emit('setCover', asset)"
        >
          <Icon
            :name="asset.provenance?.is_cover ? 'lucide:star' : 'lucide:circle-check'"
            class="size-3"
            :class="asset.provenance?.is_cover ? 'fill-current text-emerald-600' : 'text-zinc-400'"
            aria-hidden="true"
          />
          <span>{{ asset.provenance?.is_cover ? 'Primary Cover' : 'Set as Cover' }}</span>
        </button>

        <div class="flex items-center gap-1">
          <button
            type="button"
            title="Move earlier"
            class="p-1 rounded hover:bg-zinc-100 text-zinc-500 disabled:opacity-30 cursor-pointer disabled:cursor-default"
            :disabled="index === 0 || isActionLoading"
            @click="emit('move', asset, 'up')"
          >
            <Icon name="lucide:chevron-left" class="size-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            title="Move later"
            class="p-1 rounded hover:bg-zinc-100 text-zinc-500 disabled:opacity-30 cursor-pointer disabled:cursor-default"
            :disabled="index === totalInTab - 1 || isActionLoading"
            @click="emit('move', asset, 'down')"
          >
            <Icon name="lucide:chevron-right" class="size-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
