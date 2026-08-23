<script setup lang="ts">
import { computed } from "vue";

type Status = "ok" | "degraded" | "down" | "unknown";

const props = defineProps<{
  name: string;
  label?: string;
  icon?: string;
  status: Status;
  detail?: string | null | undefined;
  latencyMs?: number | null | undefined;
}>();

const displayName = computed(() => {
  if (props.label) return props.label;
  if (props.name === "api") return "API Gateway";
  if (props.name === "database") return "PostgreSQL DB";
  if (props.name === "redis") return "Redis Cache";
  if (props.name === "image_worker") return "Image Worker";
  return props.name;
});

const serviceIcon = computed(() => {
  if (props.icon) return props.icon;
  if (props.name === "api") return "lucide:server";
  if (props.name === "database") return "lucide:database";
  if (props.name === "redis") return "lucide:layers";
  if (props.name === "image_worker") return "lucide:cpu";
  return "lucide:activity";
});

const presentation = computed(() => {
  switch (props.status) {
    case "ok":
      return {
        label: "Healthy",
        badgeClass: "bg-emerald-500/10 text-emerald-700 border-emerald-500/25",
        dotClass: "bg-emerald-500",
      };
    case "degraded":
      return {
        label: "Degraded",
        badgeClass: "bg-amber-500/10 text-amber-700 border-amber-500/25",
        dotClass: "bg-amber-500",
      };
    case "down":
      return {
        label: "Unavailable",
        badgeClass: "bg-red-500/10 text-red-700 border-red-500/25",
        dotClass: "bg-red-500",
      };
    default:
      return {
        label: "Unknown",
        badgeClass: "bg-secondary text-secondary-foreground border-border",
        dotClass: "bg-muted-foreground",
      };
  }
});
</script>

<template>
  <li
    class="flex flex-col justify-between gap-3 rounded-xl border border-border bg-card p-3.5 shadow-2xs transition-all hover:border-primary/20 min-w-0"
    :data-testid="`status-${name}`"
  >
    <!-- Top Row: Service Icon & Title + Status Badge -->
    <div class="flex items-center justify-between gap-2 min-w-0">
      <div class="flex items-center gap-2 min-w-0 truncate">
        <div class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-secondary/80 text-foreground/80 border border-border/50">
          <Icon :name="serviceIcon" class="size-3.5" aria-hidden="true" />
        </div>
        <div class="min-w-0 truncate">
          <span class="text-xs font-bold tracking-tight text-foreground block truncate">
            {{ displayName }}
          </span>
          <span class="sr-only">{{ name }}</span>
        </div>
      </div>

      <span
        class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold shrink-0"
        :class="presentation.badgeClass"
      >
        <span class="size-1.5 rounded-full shrink-0" :class="presentation.dotClass" aria-hidden="true" />
        <span>{{ presentation.label }}</span>
      </span>
    </div>

    <!-- Bottom Row: Latency Metric and Subtitle Detail -->
    <div class="flex items-center justify-between gap-2 pt-1 border-t border-border/40 text-[11px] text-muted-foreground min-w-0">
      <div class="flex items-center gap-1.5 min-w-0 truncate">
        <Icon name="lucide:gauge" class="size-3 shrink-0 text-muted-foreground/70" aria-hidden="true" />
        <span v-if="latencyMs !== null && latencyMs !== undefined" class="font-mono tabular-nums font-medium text-foreground/80">
          {{ latencyMs }} ms
        </span>
        <span v-else class="font-mono text-muted-foreground/60">
          Live
        </span>
      </div>

      <span v-if="detail" class="truncate font-mono text-[10px] text-muted-foreground/70 max-w-[120px]" :title="detail">
        {{ detail }}
      </span>
      <span v-else class="text-[10px] text-muted-foreground/50 uppercase tracking-wider font-mono">
        Active
      </span>
    </div>
  </li>
</template>
