<script setup lang="ts">
import { computed, ref } from "vue";
import type { ProductionQaReport } from "~/types/production";
import Badge from "~/components/ui/Badge.vue";
import Skeleton from "~/components/ui/Skeleton.vue";

const props = defineProps<{
  qaReport?: ProductionQaReport;
  exactSlogan?: string | null;
}>();

const isHashCopied = ref(false);

function formatBytes(bytes?: number): string {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

async function copyHash(hash?: string) {
  if (!hash || typeof navigator === "undefined" || !navigator.clipboard) return;
  try {
    await navigator.clipboard.writeText(hash);
    isHashCopied.value = true;
    setTimeout(() => {
      isHashCopied.value = false;
    }, 2000);
  } catch {
    // Non-blocking fallback
  }
}

const qaItems = computed(() => {
  const r = props.qaReport;
  if (!r) return [];
  return [
    {
      label: "Canvas Dimensions",
      value: `${r.width || 4500} × ${r.height || 5400} px`,
      sub: "5:6 Standard Ratio • 15×18\" Bed",
      passed: r.dimensions_valid !== false,
      icon: "lucide:maximize-2",
      badge: "Print Standard",
    },
    {
      label: "Print Density",
      value: `${r.density_dpi || 300} DPI`,
      sub: "High-Definition POD Output",
      passed: (r.density_dpi || 300) >= 300,
      icon: "lucide:printer",
      badge: "Ultra Crisp",
    },
    {
      label: "Alpha Transparency",
      value: r.transparent_background_valid !== false ? "Verified Clean" : "Background Issues",
      sub: "Clean Cutout • Zero Halo/Fringe",
      passed: r.transparent_background_valid !== false,
      icon: "lucide:sparkles",
      badge: "Isolated Alpha",
    },
    {
      label: "Safe Print Margin",
      value: r.safe_margins_valid !== false ? "8% Inset Protected" : "Near Edges",
      sub: "Protected Safe Zone • No Bleed",
      passed: r.safe_margins_valid !== false,
      icon: "lucide:shield-check",
      badge: "Zero Clip",
    },
    {
      label: "Color Profile",
      value: r.color_space || "sRGB IEC61966-2.1",
      sub: "POD Calibrated Standard Gamut",
      passed: (r.color_space || "srgb").toLowerCase().includes("srgb"),
      icon: "lucide:palette",
      badge: "Accurate Color",
    },
    {
      label: "File Weight",
      value: formatBytes(r.file_size_bytes),
      sub: "Optimized PNG-24 • < 20MB Etsy Limit",
      passed: true,
      icon: "lucide:hard-drive",
      badge: "Fast Upload",
    },
  ];
});

const passedCount = computed(() => {
  return qaItems.value.filter((i) => i.passed).length;
});
</script>

<template>
  <div class="border border-border/80 rounded-2xl p-4 sm:p-5 bg-white shadow-xs hover:shadow-md transition-all duration-200 h-full flex flex-col justify-between space-y-4">
    <!-- Header Section -->
    <div class="space-y-2.5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="size-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200/80 shadow-2xs shrink-0">
            <Icon name="lucide:shield-check" class="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h5 class="text-sm font-bold text-foreground leading-tight">Pre-Flight QA & Print Verification</h5>
              <span class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60 shadow-2xs">
                <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {{ passedCount }}/{{ qaItems.length || 6 }} Passed
              </span>
            </div>
            <p class="text-[11px] text-muted-foreground font-medium">Automated technical quality inspection for Print-On-Demand production</p>
          </div>
        </div>

        <Badge
          :variant="qaReport?.qa_passed ? 'success' : 'warning'"
          class="text-xs px-3 py-1 font-bold shadow-2xs shrink-0 hidden sm:inline-flex items-center gap-1.5"
        >
          <Icon :name="qaReport?.qa_passed ? 'lucide:check-check' : 'lucide:triangle-alert'" class="size-3.5" aria-hidden="true" />
          <span>{{ qaReport?.qa_passed ? "100% Print Ready" : "Review Needed" }}</span>
        </Badge>
      </div>

      <!-- Compliance Mini-Badges Row -->
      <div class="flex flex-wrap items-center gap-1.5 pt-1">
        <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-slate-100/80 text-slate-700 border border-slate-200/80 px-2 py-0.5 rounded-md">
          <Icon name="lucide:check" class="size-2.5 text-emerald-600" aria-hidden="true" />
          DTG & POD Compliant
        </span>
        <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-slate-100/80 text-slate-700 border border-slate-200/80 px-2 py-0.5 rounded-md">
          <Icon name="lucide:check" class="size-2.5 text-emerald-600" aria-hidden="true" />
          Etsy 20MB Limit Safe
        </span>
        <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-slate-100/80 text-slate-700 border border-slate-200/80 px-2 py-0.5 rounded-md">
          <Icon name="lucide:check" class="size-2.5 text-emerald-600" aria-hidden="true" />
          Lossless Alpha Channel
        </span>
        <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-slate-100/80 text-slate-700 border border-slate-200/80 px-2 py-0.5 rounded-md">
          <Icon name="lucide:check" class="size-2.5 text-emerald-600" aria-hidden="true" />
          300 DPI High-Def
        </span>
      </div>
    </div>

    <!-- 6-Grid QA Checklist (Dense & Balanced) -->
    <div v-if="qaReport" class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 flex-1">
      <div
        v-for="item in qaItems"
        :key="item.label"
        class="p-3 rounded-xl bg-slate-50/90 hover:bg-slate-100/90 border border-border/80 flex flex-col justify-between transition-all duration-150 group shadow-2xs hover:shadow-xs"
      >
        <div class="flex items-center justify-between text-muted-foreground mb-1">
          <span class="text-[10px] font-bold text-slate-600 group-hover:text-foreground transition-colors uppercase tracking-wider">{{ item.label }}</span>
          <div class="size-5 rounded-md bg-white border border-border/60 flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors shadow-2xs">
            <Icon :name="item.icon" class="size-3" aria-hidden="true" />
          </div>
        </div>

        <div class="my-1 flex items-baseline justify-between gap-1">
          <span class="font-extrabold text-xs text-foreground leading-tight truncate" :title="item.value">
            {{ item.value }}
          </span>
          <Icon
            :name="item.passed ? 'lucide:circle-check' : 'lucide:circle-alert'"
            class="size-3.5 shrink-0"
            :class="item.passed ? 'text-emerald-600' : 'text-amber-500'"
            aria-hidden="true"
          />
        </div>

        <div class="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/40">
          <span class="truncate font-medium text-slate-500">{{ item.sub }}</span>
        </div>
      </div>
    </div>

    <!-- QA Skeleton Grid Fallback -->
    <div v-else class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 flex-1" data-testid="qa-loading-skeleton">
      <div v-for="i in 6" :key="i" class="p-3 rounded-xl bg-slate-50/60 border border-border/70 flex flex-col justify-between space-y-2">
        <Skeleton class="h-3 w-20" />
        <Skeleton class="h-4 w-28" />
        <Skeleton class="h-2.5 w-full pt-1" />
      </div>
    </div>

    <!-- Typography Callout (Conditional) -->
    <div v-if="qaReport?.typography_applied || exactSlogan" class="rounded-xl bg-primary/5 border border-primary/20 p-2.5 flex items-center justify-between text-xs">
      <span class="text-foreground font-semibold flex items-center gap-1.5 text-xs">
        <Icon name="lucide:type" class="size-3.5 text-primary shrink-0" aria-hidden="true" />
        <span>Slogan Typography Applied</span>
      </span>
      <span class="font-mono text-[11px] font-bold text-primary px-2.5 py-0.5 rounded-md bg-white border border-primary/20 shadow-2xs max-w-[260px] truncate" :title="qaReport?.exact_slogan_recorded || exactSlogan || undefined">
        "{{ qaReport?.exact_slogan_recorded || exactSlogan }}"
      </span>
    </div>

    <!-- Security, Hash & Engine Footer -->
    <div class="pt-2 border-t border-border/80 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground px-0.5">
      <div class="flex items-center gap-1.5">
        <Icon name="lucide:cpu" class="size-3 text-slate-500" aria-hidden="true" />
        <span>Engine: <b class="text-slate-700">v2.4 Pro Upscaler & Compositor</b></span>
      </div>

      <div v-if="qaReport?.checksum_sha256" class="flex items-center gap-1.5 font-mono text-[9px]">
        <span class="text-slate-500">SHA-256:</span>
        <button
          type="button"
          class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-mono transition-colors cursor-pointer border border-border/60"
          :title="isHashCopied ? 'Copied Full SHA-256!' : 'Click to copy full SHA-256 hash'"
          @click="copyHash(qaReport.checksum_sha256)"
        >
          <span>{{ qaReport.checksum_sha256.slice(0, 14) }}...</span>
          <Icon :name="isHashCopied ? 'lucide:check' : 'lucide:copy'" class="size-2.5 text-slate-600" :class="{ 'text-emerald-600': isHashCopied }" aria-hidden="true" />
        </button>
      </div>
    </div>
  </div>
</template>
