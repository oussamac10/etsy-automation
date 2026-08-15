<script setup lang="ts">
import { computed } from "vue";

type Status = "ok" | "degraded" | "down" | "unknown";

const props = defineProps<{
  name: string;
  status: Status;
  detail?: string | null | undefined;
  latencyMs?: number | null | undefined;
}>();

const presentation = computed(() => {
  switch (props.status) {
    case "ok":
      return {
        label: "Healthy",
        symbol: "●",
        classes: "text-emerald-800 bg-emerald-50/80 border-emerald-200 shadow-2xs",
        dotColor: "bg-emerald-500",
      };
    case "degraded":
      return {
        label: "Degraded",
        symbol: "▲",
        classes: "text-amber-900 bg-amber-50/80 border-amber-200 shadow-2xs",
        dotColor: "bg-amber-500",
      };
    case "down":
      return {
        label: "Unavailable",
        symbol: "✕",
        classes: "text-red-900 bg-red-50/80 border-red-200 shadow-2xs",
        dotColor: "bg-red-500",
      };
    default:
      return {
        label: "Unknown",
        symbol: "?",
        classes: "text-slate-700 bg-slate-50 border-slate-200 shadow-2xs",
        dotColor: "bg-slate-400",
      };
  }
});
</script>

<template>
  <li
    class="flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-sm transition-all"
    :class="presentation.classes"
    :data-testid="`status-${name}`"
  >
    <span class="font-medium tracking-tight capitalize">{{ name }}</span>
    <span class="flex items-center gap-2 text-xs">
      <span aria-hidden="true" class="text-[10px] font-bold">{{ presentation.symbol }}</span>
      <span class="font-semibold">{{ presentation.label }}</span>
      <span v-if="latencyMs !== null && latencyMs !== undefined" class="tabular-nums opacity-75 text-xs font-mono">
        {{ latencyMs }} ms
      </span>
      <span v-if="detail" class="opacity-75 font-mono text-[11px]">({{ detail }})</span>
    </span>
  </li>
</template>
