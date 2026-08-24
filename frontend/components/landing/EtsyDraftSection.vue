<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

const draftSteps = [
  { step: 1, title: "Connect Etsy Store", desc: "Authorize securely via official Etsy OAuth 2.0.", icon: "lucide:key" },
  { step: 2, title: "Create Listing Draft", desc: "Transmit titles, descriptions, price, and tags as an inactive draft.", icon: "lucide:file-plus" },
  { step: 3, title: "Upload Mockup Images", desc: "Attach high-resolution primary and secondary mockup photos.", icon: "lucide:image" },
  { step: 4, title: "Attach Digital Package", desc: "Upload the master ZIP archive containing high-res PNG assets.", icon: "lucide:package" },
  { step: 5, title: "Draft Verification", desc: "Confirm all files and taxonomy attributes before you finalize.", icon: "lucide:check-circle-2" },
];
</script>

<template>
  <section
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/60 dark:bg-stone-950/30 section-render-opt"
    aria-labelledby="etsy-draft-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
          <Icon name="lucide:store" class="size-3.5" aria-hidden="true" />
          Etsy Store Integration
        </span>
        <h2
          id="etsy-draft-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Prepare the listing. You stay in control.
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Your listing is prepared as an Etsy draft. You review and publish it directly from your Etsy Shop Manager.
        </p>
      </div>

      <!-- 5-Step Draft Workflow Visualization -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div
          v-for="(item, index) in draftSteps"
          :key="item.step"
          :class="[
            'rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-4 shadow-xs flex flex-col justify-between relative hover:-translate-y-1 hover:border-orange-500/50 hover:shadow-md transition-all duration-200 cursor-default group',
            index === draftSteps.length - 1 ? 'sm:col-span-2 lg:col-span-1' : '',
          ]"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-black text-orange-600 dark:text-orange-400 uppercase tracking-wider">
                Step {{ item.step }}
              </span>
              <div class="size-7 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-transform duration-200">
                <Icon :name="item.icon" class="size-3.5" aria-hidden="true" />
              </div>
            </div>
            <h3 class="text-xs sm:text-sm font-bold text-stone-900 dark:text-stone-100">
              {{ item.title }}
            </h3>
            <p class="text-[11px] text-stone-500 dark:text-stone-400 leading-relaxed">
              {{ item.desc }}
            </p>
          </div>

          <!-- Desktop Arrow Connector -->
          <div
            v-if="index < draftSteps.length - 1"
            class="hidden lg:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 size-6 rounded-full bg-stone-100 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 items-center justify-center shadow-2xs hover:scale-110 transition-transform duration-150"
            aria-hidden="true"
          >
            <Icon name="lucide:arrow-right" class="size-3 text-stone-400 dark:text-stone-500" />
          </div>
        </div>
      </div>

      <!-- Draft Guarantee Banner -->
      <div class="rounded-2xl border-2 border-emerald-500/30 bg-emerald-50/40 dark:bg-emerald-950/20 p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-6 shadow-sm hover:border-emerald-500/50 hover:shadow-md transition-all duration-300">
        <div class="flex items-start gap-4">
          <div class="size-12 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-md">
            <Icon name="lucide:shield-check" class="size-6" />
          </div>
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <span class="text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                Draft-Only Architecture
              </span>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-600 text-white shadow-2xs">Safe & Controlled</span>
            </div>
            <h3 class="text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">
              Zero Unreviewed Autopublishing
            </h3>
            <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400 leading-relaxed max-w-2xl">
              We never publish listings live automatically. Everything lands in your store as a complete draft, giving you final authority to review pricing, shipping profiles, and inventory before making it public.
            </p>
          </div>
        </div>

        <div class="shrink-0 text-center sm:text-right">
          <div class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white dark:bg-stone-900 border border-emerald-500/40 shadow-xs hover:scale-105 transition-transform duration-200">
            <span class="size-2 rounded-full bg-emerald-500 animate-pulse" />
            <span class="text-xs font-bold text-stone-800 dark:text-stone-200">Etsy Draft Ready ✓</span>
          </div>
        </div>
      </div>

    </div>
  </section>
</template>
