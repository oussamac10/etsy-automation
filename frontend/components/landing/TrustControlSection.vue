<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

const controlPillars = [
  {
    step: "01",
    title: "You Approve the Concept",
    desc: "Review scores, competition signals, and buyer niches before generating artwork.",
    icon: "lucide:lightbulb",
  },
  {
    step: "02",
    title: "You Approve the Artwork",
    desc: "Inspect transparent PNG cutouts, typography, and color variants before production.",
    icon: "lucide:image",
  },
  {
    step: "03",
    title: "You Review the Listing",
    desc: "Verify titles, 13 Etsy tags, structured descriptions, and IP pre-screening results.",
    icon: "lucide:file-check",
  },
  {
    step: "04",
    title: "You Publish on Etsy",
    desc: "Drafts arrive in your store safely as inactive listings. You click publish when ready.",
    icon: "lucide:store",
  },
];
</script>

<template>
  <section
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17]"
    aria-labelledby="trust-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
          <Icon name="lucide:user-check" class="size-3.5" aria-hidden="true" />
          Creator Authority
        </span>
        <h2
          id="trust-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Automation where it helps. Control where it matters.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          We believe the best digital products come from human creators paired with smart automation — never unattended autopilot bots.
        </p>
      </div>

      <!-- 4 Control Pillars Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div
          v-for="pillar in controlPillars"
          :key="pillar.step"
          class="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-6 shadow-xs space-y-3 relative flex flex-col justify-between"
        >
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-black text-orange-600 dark:text-orange-400">
                Pillar {{ pillar.step }}
              </span>
              <div class="size-9 rounded-xl bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center">
                <Icon :name="pillar.icon" class="size-4.5" />
              </div>
            </div>
            <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">
              {{ pillar.title }}
            </h3>
            <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed">
              {{ pillar.desc }}
            </p>
          </div>

          <div class="pt-2 border-t border-stone-100 dark:border-stone-800/80 flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
            <Icon name="lucide:check" class="size-3.5" />
            <span>Human-in-the-Loop</span>
          </div>
        </div>
      </div>

    </div>
  </section>
</template>
