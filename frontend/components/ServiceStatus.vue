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
        icon: "lucide:circle-check",
        classes: "text-emerald-700 bg-emerald-50 border-emerald-200 shadow-2xs",
        dotColor: "bg-emerald-500",
      };
    case "degraded":
      return {
        label: "Degraded",
        icon: "lucide:triangle-alert",
        classes: "text-amber-700 bg-amber-50 border-amber-200 shadow-2xs",
        dotColor: "bg-amber-500",
      };
    case "down":
      return {
        label: "Unavailable",
        icon: "lucide:circle-x",
        classes: "text-rose-700 bg-rose-50 border-rose-200 shadow-2xs",
        dotColor: "bg-rose-500",
      };
    default:
      return {
        label: "Unknown",
        icon: "lucide:help-circle",
        classes: "text-zinc-700 bg-zinc-50 border-zinc-200 shadow-2xs",
        dotColor: "bg-zinc-400",
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
      <Icon :name="presentation.icon" class="size-3.5 shrink-0" aria-hidden="true" />
      <span class="font-semibold">{{ presentation.label }}</span>
      <span v-if="latencyMs !== null && latencyMs !== undefined" class="tabular-nums opacity-75 text-xs font-mono">
        {{ latencyMs }} ms
      </span>
      <span v-if="detail" class="opacity-75 font-mono text-[11px]">({{ detail }})</span>
    </span>
  </li>
</template>
