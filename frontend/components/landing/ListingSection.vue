<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

const tags = [
  "radiology tech png",
  "halloween xray",
  "spooky nurse shirt",
  "skeleton coffee",
  "retro healthcare",
  "sublimation design",
  "dtg print file",
  "fall nurse gift",
  "radiologist gift",
  "xray technician",
  "vintage halloween",
  "digital download",
  "commercial use png",
];
</script>

<template>
  <section
    id="listings"
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/60 dark:bg-stone-950/30 scroll-mt-16 sm:scroll-mt-20"
    aria-labelledby="listings-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
          <Icon name="lucide:tags" class="size-3.5" aria-hidden="true" />
          Listing Optimization & SEO
        </span>
        <h2
          id="listings-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Listing copy built from your actual design.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Generate search-optimized Etsy titles, buyer-friendly cart summaries, structured descriptions, and all 13 Etsy tags derived directly from your artwork context and real file properties.
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        <!-- Left: Stylized Listing Editor Card -->
        <div
          class="lg:col-span-7 transition-all duration-700 delay-100"
          :class="[isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95']"
        >
          <div class="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-5 sm:p-7 shadow-xl space-y-5">
            
            <!-- Title Field -->
            <div class="space-y-1.5">
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-stone-700 dark:text-stone-300 flex items-center gap-1.5">
                  <Icon name="lucide:type" class="size-3.5 text-orange-600" />
                  Etsy Listing Title
                </span>
                <span class="text-[11px] text-stone-400 font-mono">128 / 140 chars</span>
              </div>
              <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-950/50 p-3 text-xs sm:text-sm font-semibold text-stone-900 dark:text-stone-100 leading-relaxed">
                Retro Radiology Halloween PNG, Spooky X-Ray Tech Sublimation Design, Skeleton Nurse Digital Download, Coffee Lover DTG Graphic
              </div>
            </div>

            <!-- Cart Summary Field -->
            <div class="space-y-1.5">
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-stone-700 dark:text-stone-300 flex items-center gap-1.5">
                  <Icon name="lucide:shopping-cart" class="size-3.5 text-blue-600" />
                  Shopping Cart Summary
                </span>
                <span class="text-[10px] uppercase font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-0.5 rounded">High Conversion</span>
              </div>
              <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-950/50 p-3 text-xs text-stone-700 dark:text-stone-300">
                Instant digital download: 1 high-resolution transparent PNG (4500x5400px at 300 DPI). Perfect for sublimation, vinyl decals, apparel printing, and creator merchandise.
              </div>
            </div>

            <!-- 13 Etsy Tags -->
            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-stone-700 dark:text-stone-300 flex items-center gap-1.5">
                  <Icon name="lucide:tags" class="size-3.5 text-purple-600" />
                  13 High-Intent Etsy Tags
                </span>
                <span class="text-[11px] font-bold text-emerald-600">13 / 13 Filled</span>
              </div>
              <div class="flex flex-wrap gap-1.5 p-3 rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-50/60 dark:bg-stone-950/40">
                <span
                  v-for="tag in tags"
                  :key="tag"
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 text-[11px] font-medium text-stone-800 dark:text-stone-200 shadow-2xs hover:scale-105 hover:-translate-y-0.5 hover:border-orange-500/50 hover:bg-orange-50/50 dark:hover:bg-stone-700 transition-all duration-150 cursor-default"
                >
                  <span class="text-orange-600 font-bold">#</span>
                  <span>{{ tag }}</span>
                </span>
              </div>
            </div>

            <!-- Structured Description Preview -->
            <div class="space-y-1.5">
              <span class="text-xs font-bold text-stone-700 dark:text-stone-300 flex items-center gap-1.5">
                <Icon name="lucide:file-text" class="size-3.5 text-amber-600" />
                Structured Product Description
              </span>
              <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-950/50 p-3 text-xs text-stone-600 dark:text-stone-400 space-y-1 font-mono leading-relaxed">
                <p class="font-bold text-stone-800 dark:text-stone-200 font-sans">📦 WHAT YOU WILL RECEIVE:</p>
                <p>• 1 × High-Resolution PNG (4500 × 5400 px, 300 DPI)</p>
                <p>• Clean transparent background with verified alpha channels</p>
                <p>• Free commercial & personal use for physical finished products</p>
              </div>
            </div>

          </div>
        </div>

        <!-- Right: Why It Works Explanations -->
        <div
          class="lg:col-span-5 space-y-5 transition-all duration-700 delay-200"
          :class="[isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6']"
        >
          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-orange-500/10 text-orange-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:search" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">SEO-Optimized Search Titles</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Front-loads primary search keywords and buyer queries while adhering strictly to Etsy's 140-character maximum.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-purple-500/10 text-purple-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:hash" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">All 13 Tags Automatically Targeted</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Never waste valuable tag slots. High-intent multi-word search phrases are generated directly from verified market demand.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:file-check" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Accurate File & Dimension Specs</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Descriptions reflect the exact dimensions, DPI, and digital deliverables created in your studio — no hallucinated specifications.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:edit-3" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Full Edit Control</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Tweak titles, rearrange tags, or personalize description notes directly in the studio prior to export.
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  </section>
</template>
