<script setup lang="ts">
// Imported explicitly rather than relying on Nuxt auto-imports, so the
// component can be mounted directly in a Vitest unit test.
import { computed } from "vue";

/**
 * One dependency's health.
 *
 * Status is never encoded by colour alone: each state carries a text label and
 * a distinct symbol (frontend/CLAUDE.md, accessibility rules).
 */
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
      return { label: "Healthy", symbol: "●", classes: "text-emerald-800 bg-emerald-50 border-emerald-300" };
    case "degraded":
      return { label: "Degraded", symbol: "▲", classes: "text-amber-900 bg-amber-50 border-amber-300" };
    case "down":
      return { label: "Unavailable", symbol: "✕", classes: "text-red-900 bg-red-50 border-red-300" };
    default:
      return { label: "Unknown", symbol: "?", classes: "text-slate-700 bg-slate-50 border-slate-300" };
  }
});
</script>

<template>
  <li
    class="flex items-center justify-between gap-3 rounded-lg border px-4 py-3"
    :class="presentation.classes"
    :data-testid="`status-${name}`"
  >
    <span class="font-medium">{{ name }}</span>
    <span class="flex items-center gap-2 text-sm">
      <span aria-hidden="true">{{ presentation.symbol }}</span>
      <span>{{ presentation.label }}</span>
      <span v-if="latencyMs !== null && latencyMs !== undefined" class="tabular-nums opacity-70">
        {{ latencyMs }} ms
      </span>
      <span v-if="detail" class="opacity-70">({{ detail }})</span>
    </span>
  </li>
</template>
