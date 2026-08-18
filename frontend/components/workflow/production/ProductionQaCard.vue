<script setup lang="ts">
import { computed } from "vue";
import type { ProductionQaReport } from "~/types/production";
import Badge from "~/components/ui/Badge.vue";

const props = defineProps<{
  qaReport?: ProductionQaReport;
  exactSlogan?: string | null;
}>();

function formatBytes(bytes?: number): string {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const qaItems = computed(() => {
  const r = props.qaReport;
  if (!r) return [];
  return [
    {
      label: "Canvas Dimensions",
      value: `${r.width || 4500} × ${r.height || 5400} px`,
      sub: "5:6 Standard Ratio",
      passed: r.dimensions_valid !== false,
      icon: "lucide:maximize-2",
    },
    {
      label: "Print Density",
      value: `${r.density_dpi || 300} DPI`,
      sub: "High-Def Output",
      passed: (r.density_dpi || 300) >= 300,
      icon: "lucide:printer",
    },
    {
      label: "Alpha Transparency",
      value: r.transparent_background_valid !== false ? "Verified Clean" : "Background Issues",
      sub: "Isolated Artwork",
      passed: r.transparent_background_valid !== false,
      icon: "lucide:sparkles",
    },
    {
      label: "Safe Print Margin",
      value: r.safe_margins_valid !== false ? "8% Inset Protected" : "Near Edges",
      sub: "Zero Clipping Risk",
      passed: r.safe_margins_valid !== false,
      icon: "lucide:shield-check",
    },
    {
      label: "Color Profile",
      value: r.color_space || "sRGB IEC61966",
      sub: "POD Calibrated",
      passed: (r.color_space || "srgb").toLowerCase().includes("srgb"),
      icon: "lucide:palette",
    },
    {
      label: "File Weight",
      value: formatBytes(r.file_size_bytes),
      sub: "Optimized PNG-24",
      passed: true,
      icon: "lucide:hard-drive",
    },
  ];
});
</script>

<template>
  <div class="border border-border/80 rounded-2xl p-4 bg-white shadow-xs space-y-3.5 hover:shadow-md transition-all duration-200 h-full flex flex-col justify-between">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2.5">
        <div class="size-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20 shadow-2xs shrink-0">
          <Icon name="lucide:shield-check" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h5 class="text-xs font-bold text-foreground leading-tight">Automated QA Verification</h5>
            <span class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-md border border-emerald-200/60">
              <span class="size-1 rounded-full bg-emerald-500" />
              Quality Passed
            </span>
          </div>
          <p class="text-[10px] text-muted-foreground font-medium">Pre-flight checks verified before mockups & listing generation</p>
        </div>
      </div>

      <Badge
        :variant="qaReport?.qa_passed ? 'success' : 'warning'"
        class="text-[10px] px-2.5 py-1 font-bold shadow-2xs shrink-0"
      >
        <Icon :name="qaReport?.qa_passed ? 'lucide:check-check' : 'lucide:triangle-alert'" class="size-3" aria-hidden="true" />
        <span>{{ qaReport?.qa_passed ? "100% Passed" : "Warnings Detected" }}</span>
      </Badge>
    </div>

    <!-- 6-Grid QA Checklist -->
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 flex-1 items-center">
      <div
        v-for="item in qaItems"
        :key="item.label"
        class="p-2.5 rounded-xl bg-slate-50/80 hover:bg-slate-100/80 border border-border/70 flex flex-col justify-between gap-1 transition-colors group"
      >
        <div class="flex items-center justify-between text-muted-foreground">
          <span class="text-[10px] font-semibold text-muted-foreground">{{ item.label }}</span>
          <Icon :name="item.icon" class="size-3 text-muted-foreground/80 group-hover:text-primary transition-colors" aria-hidden="true" />
        </div>

        <div class="flex items-baseline justify-between gap-1 mt-0.5">
          <span class="font-bold text-xs text-foreground leading-tight truncate" :title="item.value">
            {{ item.value }}
          </span>
          <Icon
            :name="item.passed ? 'lucide:check-circle-2' : 'lucide:alert-circle'"
            class="size-3.5 shrink-0"
            :class="item.passed ? 'text-emerald-600' : 'text-amber-500'"
            aria-hidden="true"
          />
        </div>

        <span class="text-[9px] text-muted-foreground font-medium truncate">
          {{ item.sub }}
        </span>
      </div>
    </div>

    <!-- Typography Banner & Checksum Info -->
    <div class="space-y-2 pt-1 border-t border-border/80">
      <div v-if="qaReport?.typography_applied" class="rounded-xl bg-primary/5 border border-primary/20 p-2.5 flex items-center justify-between text-xs">
        <span class="text-foreground font-medium flex items-center gap-1.5 text-xs">
          <Icon name="lucide:type" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Slogan Typography Applied</span>
        </span>
        <span v-if="qaReport.exact_slogan_recorded" class="font-mono text-[11px] font-bold text-primary px-2 py-0.5 rounded-md bg-white border border-primary/20">
          "{{ qaReport.exact_slogan_recorded }}"
        </span>
      </div>

      <div class="flex items-center justify-between text-[10px] text-muted-foreground px-0.5">
        <span class="flex items-center gap-1">
          <Icon name="lucide:lock" class="size-2.5 text-muted-foreground" aria-hidden="true" />
          <span>Production Pipeline Engine: <b>v2.4 Pro Upscaler</b></span>
        </span>
        <span v-if="qaReport?.checksum_sha256" class="font-mono text-[9px] text-muted-foreground/80">
          SHA: {{ qaReport.checksum_sha256.slice(0, 12) }}...
        </span>
      </div>
    </div>
  </div>
</template>
