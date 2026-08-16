<script setup lang="ts">
import { computed } from "vue";
import type { ProductionQaReport } from "~/types/production";
import Badge from "~/components/ui/Badge.vue";

const props = defineProps<{
  qaReport?: ProductionQaReport;
  exactSlogan?: string | null;
}>();

const qaItems = computed(() => {
  const r = props.qaReport;
  if (!r) return [];
  return [
    {
      label: "Exact Dimensions",
      value: `${r.width || 4500}×${r.height || 5400} px`,
      passed: r.dimensions_valid !== false,
    },
    {
      label: "Print Density",
      value: `${r.density_dpi || 300} DPI`,
      passed: (r.density_dpi || 300) >= 300,
    },
    {
      label: "Alpha Transparency",
      value: r.transparent_background_valid !== false ? "Clean Verified" : "Alpha Issues",
      passed: r.transparent_background_valid !== false,
    },
    {
      label: "Safe Margin Protected",
      value: r.safe_margins_valid !== false ? "8% Inset Protected" : "Near Canvas Edges",
      passed: r.safe_margins_valid !== false,
    },
    {
      label: "Color Space",
      value: r.color_space || "sRGB",
      passed: (r.color_space || "srgb").toLowerCase().includes("srgb"),
    },
  ];
});
</script>

<template>
  <div class="border border-zinc-200 rounded-xl p-4 bg-white space-y-3 shadow-2xs">
    <div class="flex items-center justify-between">
      <span class="text-xs font-bold text-zinc-800 flex items-center gap-1.5">
        <Icon name="lucide:shield-check" class="size-4 text-indigo-600" aria-hidden="true" />
        <span>Automated Production QA Verification</span>
      </span>
      <Badge
        :variant="qaReport?.qa_passed ? 'success' : 'warning'"
        class="text-[10px] px-2 py-0.5 font-bold"
      >
        {{ qaReport?.qa_passed ? "100% Passed" : "Warnings Detected" }}
      </Badge>
    </div>

    <!-- QA Checklist Grid -->
    <div class="grid grid-cols-2 gap-2 text-xs">
      <div
        v-for="item in qaItems"
        :key="item.label"
        class="flex items-center justify-between p-2 rounded-lg bg-zinc-50 border border-zinc-100"
      >
        <span class="text-zinc-500 text-[11px]">{{ item.label }}</span>
        <span class="font-bold flex items-center gap-1 text-[11px]" :class="item.passed ? 'text-emerald-700' : 'text-amber-700'">
          <Icon :name="item.passed ? 'lucide:check' : 'lucide:triangle-alert'" class="size-3" aria-hidden="true" />
          <span>{{ item.value }}</span>
        </span>
      </div>
    </div>

    <!-- Slogan Typography Status -->
    <div v-if="qaReport?.typography_applied" class="rounded-lg bg-indigo-50/70 border border-indigo-100 p-2.5 flex items-center justify-between text-xs">
      <span class="text-indigo-900 font-medium flex items-center gap-1.5">
        <Icon name="lucide:type" class="size-3.5 text-indigo-600" aria-hidden="true" />
        <span>Slogan Typography Applied</span>
      </span>
      <span v-if="qaReport.exact_slogan_recorded" class="font-mono text-[11px] font-bold text-indigo-950">
        "{{ qaReport.exact_slogan_recorded }}"
      </span>
    </div>
  </div>
</template>
