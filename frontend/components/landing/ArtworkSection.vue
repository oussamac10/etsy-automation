<script setup lang="ts">
import { ref } from "vue";
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();
const previewBg = ref<"transparent" | "white" | "dark">("transparent");
</script>

<template>
  <section
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/60 dark:bg-stone-950/30"
    aria-labelledby="artwork-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-xs font-semibold">
          <Icon name="lucide:wand-sparkles" class="size-3.5" aria-hidden="true" />
          Artwork & Master Assets
        </span>
        <h2
          id="artwork-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Turn the opportunity into production-ready artwork.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Generate clean high-resolution digital artwork with true transparent backgrounds, distinct typography, and automatic adaptation for light and dark garments.
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        <!-- Left: Interactive Asset Preview Canvas -->
        <div
          class="lg:col-span-7 transition-all duration-700 delay-100"
          :class="[isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95']"
        >
          <div class="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-xl overflow-hidden">
            
            <!-- Canvas Header & Background Mode Toggle -->
            <div class="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-stone-100 dark:border-stone-800 bg-stone-50/70 dark:bg-stone-950/40">
              <div class="flex items-center gap-2">
                <span class="size-2.5 rounded-full bg-emerald-500" />
                <span class="text-xs font-bold text-stone-700 dark:text-stone-300">Master Asset: 4500 × 5400px (300 DPI)</span>
              </div>

              <!-- BG Switcher -->
              <div class="flex items-center gap-1 bg-stone-200/80 dark:bg-stone-800 p-0.5 rounded-lg text-xs" role="group" aria-label="Preview Background Color">
                <button
                  type="button"
                  :class="[
                    'px-2 py-1 rounded text-[11px] font-semibold transition-all cursor-pointer',
                    previewBg === 'transparent' ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-2xs' : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200',
                  ]"
                  @click="previewBg = 'transparent'"
                >
                  Alpha
                </button>
                <button
                  type="button"
                  :class="[
                    'px-2 py-1 rounded text-[11px] font-semibold transition-all cursor-pointer',
                    previewBg === 'white' ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-2xs' : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200',
                  ]"
                  @click="previewBg = 'white'"
                >
                  Light Tee
                </button>
                <button
                  type="button"
                  :class="[
                    'px-2 py-1 rounded text-[11px] font-semibold transition-all cursor-pointer',
                    previewBg === 'dark' ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-2xs' : 'text-stone-500 hover:text-stone-800 dark:hover:text-stone-200',
                  ]"
                  @click="previewBg = 'dark'"
                >
                  Dark Tee
                </button>
              </div>
            </div>

            <!-- Artwork Display Box -->
            <div
              :class="[
                'relative h-72 sm:h-96 flex items-center justify-center p-6 transition-colors duration-300 overflow-hidden',
                previewBg === 'transparent' ? 'bg-alpha-grid bg-stone-100/80 dark:bg-stone-900/80' : '',
                previewBg === 'white' ? 'bg-white text-stone-900' : '',
                previewBg === 'dark' ? 'bg-stone-950 text-white' : '',
              ]"
            >
              <!-- Graphic Representation (Pure Transparent PNG Cutout Artwork) -->
              <div class="relative z-10 text-center max-w-xs space-y-3 hover:scale-105 transition-transform duration-300 cursor-pointer filter drop-shadow-xl">
                <!-- Cutout Artwork Vector (No solid dark box) -->
                <div class="relative size-28 sm:size-36 mx-auto flex items-center justify-center">
                  <div class="absolute inset-0 rounded-full bg-gradient-to-tr from-amber-500/20 via-orange-500/25 to-rose-500/20 blur-md" />
                  <Icon
                    name="lucide:sparkles"
                    class="size-20 sm:size-24 text-orange-500 filter drop-shadow-md animate-spin-slow transition-transform duration-300"
                    aria-hidden="true"
                  />
                </div>

                <div>
                  <h4
                    class="text-base sm:text-lg font-black tracking-widest uppercase transition-colors duration-300"
                    :class="[
                      previewBg === 'dark' ? 'text-white' : 'text-stone-900 dark:text-stone-100',
                    ]"
                  >
                    SPOOKY X-RAY SQUAD
                  </h4>
                  <p
                    class="text-xs font-semibold tracking-wide transition-colors duration-300"
                    :class="[previewBg === 'dark' ? 'text-stone-300' : 'text-stone-600 dark:text-stone-400']"
                  >
                    Est. 2026 · Pure Transparent PNG Cutout
                  </p>
                </div>
              </div>

              <!-- Quality Stamp Badge -->
              <div class="absolute bottom-3 left-3 bg-white/90 dark:bg-stone-900/90 border border-stone-200 dark:border-stone-800 rounded-lg px-2.5 py-1 text-[10px] font-bold text-stone-700 dark:text-stone-300 shadow-2xs backdrop-blur-xs flex items-center gap-1.5 hover:scale-105 transition-transform duration-200">
                <Icon name="lucide:check-circle" class="size-3 text-emerald-600" />
                <span>300 DPI Print-Ready PNG</span>
              </div>
            </div>

          </div>
        </div>

        <!-- Right: Feature Explanations -->
        <div
          class="lg:col-span-5 space-y-5 transition-all duration-700 delay-200"
          :class="[isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6']"
        >
          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-orange-500/10 text-orange-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:layers" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">True Alpha Transparency</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Edges are preserved with clean alpha cutouts — ready for direct-to-garment (DTG), direct-to-film (DTF), or sublimation printing.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:maximize" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">High-Resolution Master Files</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                4500 × 5400 pixel master exports ensure sharp raster clarity for large apparel prints, posters, and stickers.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-purple-500/10 text-purple-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:palette" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">Light & Dark Variant Support</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Easily generate inverted or color-adapted variants so typography and graphics remain readable across black, white, or pastel fabrics.
              </p>
            </div>
          </div>

          <div class="flex items-start gap-3.5 hover:translate-x-1.5 transition-transform duration-200 cursor-default group">
            <div class="size-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 transition-transform duration-200">
              <Icon name="lucide:user-check" class="size-5" />
            </div>
            <div>
              <h3 class="text-base font-bold text-stone-900 dark:text-stone-100">You Hold Creative Approval</h3>
              <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-0.5">
                Review artwork candidates, request prompt refinements, or approve the exact master before production begins.
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  </section>
</template>
