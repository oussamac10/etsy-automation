<script setup lang="ts">
import { ref } from "vue";
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();
const activeStep = ref(1);

const timelineSteps = [
  {
    step: 1,
    title: "Find an Opportunity",
    desc: "Discover demand-backed product niches with real-time scoring, trend curves, and seasonal timing signals.",
    icon: "lucide:search",
  },
  {
    step: 2,
    title: "Create Artwork",
    desc: "Synthesize 300 DPI master PNG files with crisp alpha transparency, bespoke typography, and garment variants.",
    icon: "lucide:image",
  },
  {
    step: 3,
    title: "Build Mockups",
    desc: "Automatically map artwork across 9 standard catalog items with realistic perspective, shadows, and textures.",
    icon: "lucide:shirt",
  },
  {
    step: 4,
    title: "Optimize Listing",
    desc: "Generate high-ranking Etsy titles, shopping cart summaries, formatted descriptions, and all 13 Etsy tags.",
    icon: "lucide:tags",
  },
  {
    step: 5,
    title: "Create Etsy Draft",
    desc: "Export the verified package and mockups directly to your Etsy shop as an inactive draft for your review.",
    icon: "lucide:store",
  },
];
</script>

<template>
  <section
    id="how-it-works"
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] scroll-mt-16 sm:scroll-mt-20 section-render-opt"
    aria-labelledby="how-it-works-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12 sm:space-y-16">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
          <Icon name="lucide:git-commit" class="size-3.5" aria-hidden="true" />
          5-Step Studio Workflow
        </span>
        <h2
          id="how-it-works-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          From market opportunity to Etsy draft in one workflow.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Five structured stages designed to give digital creators speed without sacrificing creative review.
        </p>
      </div>

      <!-- Desktop Connected Horizontal Timeline -->
      <div class="hidden lg:block relative pt-6">
        <!-- Connecting Line Behind Nodes -->
        <div class="absolute top-[48px] left-[10%] right-[10%] h-1 bg-stone-200 dark:bg-stone-800 -z-0">
          <div
            class="h-full bg-orange-600 transition-all duration-500"
            :style="{ width: `${((activeStep - 1) / (timelineSteps.length - 1)) * 100}%` }"
          />
        </div>

        <div class="grid grid-cols-5 gap-4 relative z-10">
          <div
            v-for="item in timelineSteps"
            :key="item.step"
            class="flex flex-col items-center text-center space-y-3 cursor-pointer group"
            @click="activeStep = item.step"
          >
            <!-- Step Circle Indicator -->
            <div
              :class="[
                'size-14 rounded-2xl flex items-center justify-center font-black text-sm transition-all duration-200 shadow-md group-hover:-translate-y-1 group-hover:shadow-lg',
                activeStep === item.step
                  ? 'bg-orange-600 text-white scale-110 ring-4 ring-orange-500/20'
                  : item.step < activeStep
                    ? 'bg-emerald-600 text-white'
                    : 'bg-white dark:bg-stone-900 border-2 border-stone-300 dark:border-stone-700 text-stone-700 dark:text-stone-300 group-hover:border-orange-500',
              ]"
            >
              <Icon v-if="item.step < activeStep" name="lucide:check" class="size-6" />
              <Icon v-else :name="item.icon" class="size-6 group-hover:scale-110 transition-transform duration-200" />
            </div>

            <!-- Step Label & Title -->
            <div class="space-y-1">
              <span class="text-[10px] font-black uppercase tracking-wider text-orange-600 dark:text-orange-400">
                Step 0{{ item.step }}
              </span>
              <h3 class="text-sm font-bold text-stone-900 dark:text-stone-100 group-hover:text-orange-600 dark:group-hover:text-orange-400 transition-colors">
                {{ item.title }}
              </h3>
              <p class="text-xs text-stone-500 dark:text-stone-400 leading-relaxed px-1">
                {{ item.desc }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Mobile / Tablet Vertical Connected Timeline -->
      <div class="lg:hidden relative space-y-4 sm:space-y-6">
        <!-- Exact Center Spine with Gradient Glow -->
        <div class="absolute left-[18px] sm:left-[22px] top-6 bottom-6 w-0.5 -translate-x-1/2 bg-gradient-to-b from-orange-500 via-amber-500 to-emerald-500 rounded-full" aria-hidden="true" />

        <div
          v-for="(item, index) in timelineSteps"
          :key="item.step"
          class="relative flex items-start gap-3 sm:gap-4 transition-all duration-500"
          :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
          :style="{ transitionDelay: `${index * 100}ms` }"
          @click="activeStep = item.step"
        >
          <!-- Node Dot on Spine: Exact 36px / 44px centered on spine line -->
          <div class="relative shrink-0 flex items-center justify-center pt-3.5">
            <div
              :class="[
                'size-9 sm:size-11 rounded-xl flex items-center justify-center font-black text-xs shadow-md transition-all duration-300 cursor-pointer z-10',
                activeStep === item.step
                  ? 'bg-orange-600 text-white scale-110 ring-4 ring-orange-500/25 shadow-orange-500/30'
                  : item.step < activeStep
                    ? 'bg-emerald-600 text-white shadow-emerald-500/20'
                    : 'bg-white dark:bg-stone-900 border-2 border-stone-300 dark:border-stone-700 text-stone-700 dark:text-stone-300 hover:border-orange-500 hover:scale-105',
              ]"
            >
              <Icon v-if="item.step < activeStep" name="lucide:check" class="size-4 sm:size-5" />
              <Icon v-else :name="item.icon" class="size-4 sm:size-5" />
            </div>
          </div>

          <!-- Step Content Card -->
          <div
            :class="[
              'flex-1 rounded-2xl border transition-all duration-300 p-4 sm:p-5 shadow-xs backdrop-blur-xs cursor-pointer group',
              activeStep === item.step
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-md ring-1 ring-orange-500/20 -translate-y-0.5'
                : 'border-stone-200/80 dark:border-stone-800 bg-white/80 dark:bg-stone-900/60 hover:border-orange-500/40 hover:bg-white dark:hover:bg-stone-900 hover:-translate-y-0.5',
            ]"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="inline-flex items-center gap-1 text-[10px] font-black uppercase tracking-widest text-orange-600 dark:text-orange-400 bg-orange-500/10 dark:bg-orange-500/15 px-2.5 py-0.5 rounded-md">
                Stage 0{{ item.step }}
              </span>
              <span class="text-[10px] font-semibold text-stone-400 dark:text-stone-500">
                Step {{ item.step }} of 5
              </span>
            </div>

            <h3 class="text-base font-bold text-stone-900 dark:text-stone-100 mt-1.5 group-hover:text-orange-600 dark:group-hover:text-orange-400 transition-colors">
              {{ item.title }}
            </h3>

            <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed mt-1">
              {{ item.desc }}
            </p>
          </div>
        </div>
      </div>

    </div>
  </section>
</template>
