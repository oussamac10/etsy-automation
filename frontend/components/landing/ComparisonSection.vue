<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

const withoutAppPoints = [
  "Fragmented keyword search across disconnected tools",
  "Guessing what to design without demand or competition scores",
  "Manual prompt trial-and-error with inconsistent raster output",
  "Manual background removal and upscaling in separate editors",
  "Creating light/dark garment variations manually",
  "Designing mockups in Photoshop or Canva one item at a time",
  "Brainstorming 13 tags and writing listing copy from scratch",
  "Manually checking USPTO trademark registries for phrase risks",
  "Assembling ZIP packages and manual Etsy upload",
];

const withAppPoints = [
  "Integrated market research with demand & competition scores",
  "3 guided idea modes: Market-Led, User Idea, or Hybrid",
  "High-resolution 300 DPI master PNGs with clean alpha transparency",
  "Automatic typography placement and variant generation",
  "Instant mockup placement across 9 standard catalog products",
  "SEO-optimized titles, cart summaries, and 13 high-intent tags",
  "Automated preliminary trademark screening before export",
  "Safe, inactive Etsy draft export ready for your review",
  "Complete human-in-the-loop creative control at every milestone",
];
</script>

<template>
  <section
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/60 dark:bg-stone-950/30 section-render-opt"
    aria-labelledby="comparison-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-stone-500/10 border border-stone-500/20 text-stone-700 dark:text-stone-300 text-xs font-semibold">
          <Icon name="lucide:scale" class="size-3.5" aria-hidden="true" />
          Workflow Comparison
        </span>
        <h2
          id="comparison-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Everything in one unified studio.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Replace a disconnected stack of tabs, tools, and spreadsheets with one streamlined workspace.
        </p>
      </div>

      <!-- Side-by-Side Comparison Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8 items-stretch">
        
        <!-- Without App Card -->
        <div class="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white/70 dark:bg-stone-900/70 p-6 sm:p-8 space-y-5 shadow-xs">
          <div class="flex items-center gap-3 border-b border-stone-100 dark:border-stone-800 pb-4">
            <div class="size-10 rounded-xl bg-stone-100 dark:bg-stone-800 text-stone-500 flex items-center justify-center">
              <Icon name="lucide:x" class="size-5" />
            </div>
            <div>
              <span class="text-[10px] font-black uppercase tracking-wider text-stone-400">The Fragmented Way</span>
              <h3 class="text-lg font-bold text-stone-800 dark:text-stone-200">Without the Studio</h3>
            </div>
          </div>

          <ul class="space-y-3 text-xs sm:text-sm text-stone-600 dark:text-stone-400">
            <li v-for="point in withoutAppPoints" :key="point" class="flex items-start gap-2.5">
              <Icon name="lucide:x-circle" class="size-4 text-red-400 shrink-0 mt-0.5" />
              <span>{{ point }}</span>
            </li>
          </ul>
        </div>

        <!-- With App Card (Highlighted) -->
        <div class="rounded-2xl border-2 border-orange-500 bg-white dark:bg-stone-900 p-6 sm:p-8 space-y-5 shadow-xl relative overflow-hidden">
          <div class="absolute top-0 right-0 transform translate-x-6 -translate-y-6 size-32 rounded-full bg-orange-400/10 blur-2xl pointer-events-none" />

          <div class="flex items-center gap-3 border-b border-stone-100 dark:border-stone-800 pb-4">
            <div class="size-10 rounded-xl bg-orange-600 text-white flex items-center justify-center shadow-xs">
              <Icon name="lucide:sparkles" class="size-5" />
            </div>
            <div>
              <span class="text-[10px] font-black uppercase tracking-wider text-orange-600 dark:text-orange-400">The Modern Studio</span>
              <h3 class="text-lg font-black text-stone-900 dark:text-stone-100">With NovaCraftPixel</h3>
            </div>
          </div>

          <ul class="space-y-3 text-xs sm:text-sm text-stone-800 dark:text-stone-200 font-medium">
            <li v-for="point in withAppPoints" :key="point" class="flex items-start gap-2.5">
              <Icon name="lucide:check-circle-2" class="size-4 text-orange-600 dark:text-orange-500 shrink-0 mt-0.5" />
              <span>{{ point }}</span>
            </li>
          </ul>
        </div>

      </div>

    </div>
  </section>
</template>
