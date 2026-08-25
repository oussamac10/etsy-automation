<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();
</script>

<template>
  <section
    id="safety"
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] scroll-mt-16 sm:scroll-mt-20 section-render-opt"
    aria-labelledby="ip-safety-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
          <Icon name="lucide:shield-check" class="size-3.5" aria-hidden="true" />
          Intellectual Property Screening
        </span>
        <h2
          id="ip-safety-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Catch obvious phrase risks before you list.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Preliminary automated screening checks design titles, multi-word phrases, and keywords against active trademark records to help you spot brand name conflicts early.
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        <!-- Left: IP Screening Results Mock Card -->
        <div
          class="lg:col-span-7 transition-all duration-700 delay-100"
          :class="[isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95']"
        >
          <div class="rounded-2xl border border-emerald-500/30 bg-white dark:bg-stone-900 p-6 sm:p-8 shadow-xl space-y-5 relative">
            
            <!-- Header Status -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 dark:border-stone-800 pb-4">
              <div class="flex items-center gap-3">
                <div class="size-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                  <Icon name="lucide:shield-check" class="size-5" />
                </div>
                <div>
                  <h3 class="text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">
                    Preliminary Risk Assessment
                  </h3>
                  <span class="text-xs text-stone-500">Searched phrases across trademark databases</span>
                </div>
              </div>

              <div class="px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-bold flex items-center gap-1.5 shadow-2xs self-start sm:self-auto">
                <span class="size-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Low Risk Level</span>
              </div>
            </div>

            <!-- Checked Phrases List -->
            <div class="space-y-2 text-xs">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-2 p-2.5 rounded-lg bg-stone-50 dark:bg-stone-800/40 border border-stone-100 dark:border-stone-800 hover:translate-x-1 hover:border-emerald-500/40 hover:bg-emerald-50/20 dark:hover:bg-emerald-950/20 transition-all duration-150 cursor-default">
                <div class="flex items-center gap-2 min-w-0">
                  <Icon name="lucide:check-circle-2" class="size-4 text-emerald-600 shrink-0" />
                  <span class="font-semibold text-stone-800 dark:text-stone-200">"Retro Radiology Halloween"</span>
                </div>
                <span class="text-[11px] text-stone-500 pl-6 sm:pl-0">0 active registered brand conflicts</span>
              </div>

              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-2 p-2.5 rounded-lg bg-stone-50 dark:bg-stone-800/40 border border-stone-100 dark:border-stone-800 hover:translate-x-1 hover:border-emerald-500/40 hover:bg-emerald-50/20 dark:hover:bg-emerald-950/20 transition-all duration-150 cursor-default">
                <div class="flex items-center gap-2 min-w-0">
                  <Icon name="lucide:check-circle-2" class="size-4 text-emerald-600 shrink-0" />
                  <span class="font-semibold text-stone-800 dark:text-stone-200">"Spooky X-Ray Tech Sublimation"</span>
                </div>
                <span class="text-[11px] text-stone-500 pl-6 sm:pl-0">Generic descriptive phrase</span>
              </div>

              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-2 p-2.5 rounded-lg bg-stone-50 dark:bg-stone-800/40 border border-stone-100 dark:border-stone-800 hover:translate-x-1 hover:border-emerald-500/40 hover:bg-emerald-50/20 dark:hover:bg-emerald-950/20 transition-all duration-150 cursor-default">
                <div class="flex items-center gap-2 min-w-0">
                  <Icon name="lucide:check-circle-2" class="size-4 text-emerald-600 shrink-0" />
                  <span class="font-semibold text-stone-800 dark:text-stone-200">"Skeleton Nurse Digital Download"</span>
                </div>
                <span class="text-[11px] text-stone-500 pl-6 sm:pl-0">Common commercial terminology</span>
              </div>
            </div>

            <!-- Mandatory Legal Disclaimer Alert -->
            <div class="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 flex items-start gap-3">
              <Icon name="lucide:info" class="size-4 text-amber-500 shrink-0 mt-0.5" />
              <p class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed">
                <span class="font-semibold text-foreground">Notice:</span> Preliminary automated trademark screening only — not legal advice. Always conduct independent due diligence with relevant trademark authorities for your jurisdiction.
              </p>
            </div>
          </div>
        </div>

        <!-- Right: Why Pre-Screening Matters -->
        <div
          class="lg:col-span-5 space-y-5 transition-all duration-700 delay-200"
          :class="[isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6']"
        >
          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:search-check" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Automated Phrase Screening</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Evaluates keyword combinations before they enter titles or tags, highlighting potential direct trademark matches.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:file-search" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Live Database Checks</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Matches candidate phrases against official trademark records in relevant product classes (e.g. apparel, stationery, print on demand).
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-purple-500/10 text-purple-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:user-x" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Creator Review Checkpoint</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                If a moderate or high risk phrase is flagged, you are prompted to review, edit, or remove the term before creating a draft.
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  </section>
</template>
