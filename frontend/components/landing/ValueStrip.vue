<script setup lang="ts">
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();

const steps = [
  {
    step: "01",
    title: "Market Research",
    desc: "Scan real-time demand, buyer intent & seasonal timing signals.",
    icon: "lucide:search",
  },
  {
    step: "02",
    title: "Artwork Studio",
    desc: "Generate 300 DPI transparent PNGs with typography & variant support.",
    icon: "lucide:image",
  },
  {
    step: "03",
    title: "Realistic Mockups",
    desc: "Place artwork automatically across 9 standard creator items.",
    icon: "lucide:shirt",
  },
  {
    step: "04",
    title: "Listing SEO",
    desc: "Format high-ranking titles, descriptions, and 13 Etsy tags.",
    icon: "lucide:tags",
  },
  {
    step: "05",
    title: "Etsy Drafts",
    desc: "Export verified drafts straight to your Etsy store for manual publish.",
    icon: "lucide:store",
  },
];
</script>

<template>
  <section
    ref="targetRef"
    class="border-y border-stone-200/80 dark:border-stone-800 bg-[#FFFDF7]/80 dark:bg-stone-950/40 py-12 sm:py-16 relative overflow-hidden"
    aria-label="Workflow Stages Overview"
  >
    <!-- Ambient Background Glow -->
    <div class="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden" aria-hidden="true">
      <div class="size-[450px] rounded-full bg-orange-500/5 dark:bg-orange-500/10 blur-3xl" />
    </div>

    <div class="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 sm:gap-4.5">
        <div
          v-for="(item, index) in steps"
          :key="item.step"
          :class="[
            'group rounded-2xl border border-stone-200/80 dark:border-stone-800/90 bg-white/80 dark:bg-stone-900/80 p-5 shadow-2xs backdrop-blur-xs flex flex-col justify-between hover:-translate-y-1.5 hover:border-orange-500/40 hover:shadow-md dark:hover:border-orange-500/40 transition-all duration-300 cursor-default',
            index === 4 ? 'sm:col-span-2 lg:col-span-1' : '',
            isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6',
          ]"
          :style="{ transitionDelay: `${index * 80}ms` }"
        >
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-[10px] font-black uppercase tracking-widest text-stone-400 dark:text-stone-500 group-hover:text-orange-600 dark:group-hover:text-orange-400 transition-colors">
                Step {{ item.step }}
              </span>
              <div class="size-9 rounded-xl bg-orange-500/10 dark:bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-2xs group-hover:bg-orange-600 group-hover:text-white group-hover:scale-110 group-hover:rotate-3 transition-all duration-300">
                <Icon :name="item.icon" class="size-4.5" aria-hidden="true" />
              </div>
            </div>

            <h2 class="text-sm sm:text-base font-bold text-stone-900 dark:text-stone-100 group-hover:text-orange-600 dark:group-hover:text-orange-400 transition-colors">
              {{ item.title }}
            </h2>

            <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed">
              {{ item.desc }}
            </p>
          </div>

          <!-- Bottom Micro-Progress Indicator -->
          <div class="pt-3 mt-2 border-t border-stone-100 dark:border-stone-800/80 flex items-center justify-between text-[10px] font-semibold text-stone-400 dark:text-stone-500">
            <span>Stage {{ index + 1 }} of 5</span>
            <Icon name="lucide:arrow-right" class="size-3 text-stone-300 dark:text-stone-600 group-hover:text-orange-500 group-hover:translate-x-0.5 transition-all" aria-hidden="true" />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
