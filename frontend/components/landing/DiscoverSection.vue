<script setup lang="ts">
import { ref, watch } from "vue";
import { useScrollReveal } from "~/composables/useScrollReveal";

const { targetRef, isVisible } = useScrollReveal();
const activeModeTab = ref<"market-led" | "user-idea" | "hybrid">("market-led");
const displayScore = ref(0);

watch(isVisible, (visible) => {
  if (visible && displayScore.value === 0) {
    const target = 89;
    const duration = 1200;
    const start = performance.now();
    const animate = (time: number) => {
      const elapsed = time - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      displayScore.value = Math.round(ease * target);
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }
});
</script>

<template>
  <section
    id="discover"
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] scroll-mt-16 sm:scroll-mt-20"
    aria-labelledby="discover-heading"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-12 sm:space-y-16">
      
      <!-- Section Header -->
      <div
        class="max-w-3xl mx-auto text-center space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
          <Icon name="lucide:search" class="size-3.5" aria-hidden="true" />
          Market Intelligence
        </span>
        <h2
          id="discover-heading"
          class="text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100"
        >
          Don't know what to design next?
        </h2>
        <p class="text-sm sm:text-base lg:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Discover market opportunities using demand, competition, seasonal timing, buyer intent, product fit, and trend signals.
        </p>
      </div>

      <!-- Mode Selector Pills -->
      <div class="flex items-center justify-center gap-1 sm:gap-2 max-w-md mx-auto p-1 rounded-xl bg-stone-200/60 dark:bg-stone-900 border border-stone-300/60 dark:border-stone-800">
        <button
          type="button"
          :class="[
            'flex-1 py-1.5 sm:py-2 px-2 sm:px-3 rounded-lg text-[11px] sm:text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1 sm:gap-1.5 whitespace-nowrap',
            activeModeTab === 'market-led'
              ? 'bg-white dark:bg-stone-800 text-orange-600 dark:text-orange-400 shadow-xs'
              : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200',
          ]"
          @click="activeModeTab = 'market-led'"
        >
          <Icon name="lucide:search" class="size-3.5 shrink-0" aria-hidden="true" />
          <span>Discover Ideas</span>
        </button>

        <button
          type="button"
          :class="[
            'flex-1 py-1.5 sm:py-2 px-2 sm:px-3 rounded-lg text-[11px] sm:text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1 sm:gap-1.5 whitespace-nowrap',
            activeModeTab === 'user-idea'
              ? 'bg-white dark:bg-stone-800 text-orange-600 dark:text-orange-400 shadow-xs'
              : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200',
          ]"
          @click="activeModeTab = 'user-idea'"
        >
          <Icon name="lucide:lightbulb" class="size-3.5 shrink-0" aria-hidden="true" />
          <span>Use My Idea</span>
        </button>

        <button
          type="button"
          :class="[
            'flex-1 py-1.5 sm:py-2 px-2 sm:px-3 rounded-lg text-[11px] sm:text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1 sm:gap-1.5 whitespace-nowrap',
            activeModeTab === 'hybrid'
              ? 'bg-white dark:bg-stone-800 text-orange-600 dark:text-orange-400 shadow-xs'
              : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200',
          ]"
          @click="activeModeTab = 'hybrid'"
        >
          <Icon name="lucide:git-merge" class="size-3.5 shrink-0" aria-hidden="true" />
          <span>Hybrid</span>
        </button>
      </div>

      <!-- Feature Visual Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        <!-- Left: Realistic Opportunity Card -->
        <div
          class="lg:col-span-7 transition-all duration-700 delay-100"
          :class="[isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-6']"
        >
          <div class="rounded-2xl border-2 border-orange-500/30 bg-white dark:bg-stone-900 p-4 sm:p-7 shadow-xl relative overflow-hidden">
            <div class="absolute top-0 right-0 transform translate-x-6 -translate-y-6 size-32 rounded-full bg-orange-400/10 blur-2xl pointer-events-none" />

            <!-- Card Header -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 dark:border-stone-800 pb-4">
              <div>
                <div class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-orange-600 text-white">
                  <Icon name="lucide:award" class="size-3" aria-hidden="true" />
                  <span>Best Opportunity</span>
                </div>
                <h3 class="text-lg sm:text-2xl font-black text-stone-900 dark:text-stone-100 mt-1.5">
                  Retro Radiology Halloween
                </h3>
              </div>

              <!-- Score Badge -->
              <div class="flex items-center gap-2 rounded-xl bg-orange-50 dark:bg-orange-950/40 border border-orange-200/80 dark:border-orange-900/60 px-3.5 py-2 hover:scale-105 transition-transform duration-200 shadow-2xs self-start sm:self-auto">
                <Icon name="lucide:gauge" class="size-5 text-orange-600 dark:text-orange-400" aria-hidden="true" />
                <div>
                  <span class="text-[10px] font-bold text-stone-500 uppercase block leading-none">Score</span>
                  <span class="text-lg font-black text-orange-600 dark:text-orange-400 leading-none">
                    {{ displayScore || 89 }}<span class="text-xs text-stone-400 font-normal">/100</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- Signal Metric Chips Grid -->
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 py-4 text-xs">
              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">Trend Trajectory</span>
                <span class="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-0.5">
                  <Icon name="lucide:trending-up" class="size-3.5" /> Rising
                </span>
              </div>

              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">Competition</span>
                <span class="font-bold text-stone-800 dark:text-stone-200 flex items-center gap-1 mt-0.5">
                  <Icon name="lucide:scale" class="size-3.5" /> Medium
                </span>
              </div>

              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">Seasonal Timing</span>
                <span class="font-bold text-orange-600 flex items-center gap-1 mt-0.5">
                  <Icon name="lucide:flame" class="size-3.5" /> Sell Now
                </span>
              </div>

              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">Demand Validation</span>
                <span class="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-0.5">
                  <Icon name="lucide:check-circle" class="size-3.5" /> Strong
                </span>
              </div>

              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">IP Risk Review</span>
                <span class="font-bold text-emerald-600 flex items-center gap-1 mt-0.5">
                  <Icon name="lucide:shield-check" class="size-3.5" /> Low Risk
                </span>
              </div>

              <div class="rounded-xl border border-stone-100 dark:border-stone-800 bg-stone-50/80 dark:bg-stone-800/40 p-3 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-md transition-all duration-200 cursor-default">
                <span class="text-[11px] text-stone-500 block">Best For</span>
                <span class="font-bold text-stone-800 dark:text-stone-200 flex items-center gap-1 mt-0.5 truncate">
                  <Icon name="lucide:shirt" class="size-3.5 shrink-0" /> T-Shirt · Sweatshirt
                </span>
              </div>
            </div>

            <!-- Why This Could Sell Callout -->
            <div class="rounded-xl border border-orange-200/80 dark:border-orange-900/60 bg-orange-50/60 dark:bg-orange-950/20 p-3.5 text-xs sm:text-sm text-stone-800 dark:text-stone-200">
              <span class="font-bold text-orange-700 dark:text-orange-400 block mb-0.5">Why This Could Sell</span>
              "Strong seasonal intent combined with a specific professional audience of healthcare staff and radiology technicians looking for festive apparel."
            </div>

            <!-- Clarity Disclaimer -->
            <p class="mt-3 text-[11px] text-stone-400 dark:text-stone-500 text-center italic">
              Signals derived from keyword patterns, competition density, and seasonal timing models — not guarantees of individual sales.
            </p>
          </div>
        </div>

        <!-- Right: 3 Discovery Approaches Explanation -->
        <div
          class="lg:col-span-5 space-y-4 transition-all duration-700 delay-200"
          :class="[isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6']"
        >
          <div
            :class="[
              'rounded-xl p-4 border transition-all',
              activeModeTab === 'market-led'
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-sm'
                : 'border-stone-200 dark:border-stone-800 bg-white/50 dark:bg-stone-900/50 opacity-75',
            ]"
            @click="activeModeTab = 'market-led'"
          >
            <div class="flex items-center gap-2.5 mb-1.5">
              <div class="size-7 rounded-lg bg-orange-500/10 text-orange-600 flex items-center justify-center">
                <Icon name="lucide:search" class="size-4" />
              </div>
              <h3 class="text-sm font-bold text-stone-900 dark:text-stone-100">Market-Led Discovery</h3>
            </div>
            <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed pl-9.5">
              Target a buyer niche or product type. The engine scans demand signals and generates 3 high-potential concepts with actionable scores.
            </p>
          </div>

          <div
            :class="[
              'rounded-xl p-4 border transition-all',
              activeModeTab === 'user-idea'
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-sm'
                : 'border-stone-200 dark:border-stone-800 bg-white/50 dark:bg-stone-900/50 opacity-75',
            ]"
            @click="activeModeTab = 'user-idea'"
          >
            <div class="flex items-center gap-2.5 mb-1.5">
              <div class="size-7 rounded-lg bg-blue-500/10 text-blue-600 flex items-center justify-center">
                <Icon name="lucide:lightbulb" class="size-4" />
              </div>
              <h3 class="text-sm font-bold text-stone-900 dark:text-stone-100">Use My Idea</h3>
            </div>
            <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed pl-9.5">
              Bring your own slogan, quote, or design concept. The engine validates market appeal, refines keywords, and crafts production prompts.
            </p>
          </div>

          <div
            :class="[
              'rounded-xl p-4 border transition-all',
              activeModeTab === 'hybrid'
                ? 'border-orange-500 bg-white dark:bg-stone-900 shadow-sm'
                : 'border-stone-200 dark:border-stone-800 bg-white/50 dark:bg-stone-900/50 opacity-75',
            ]"
            @click="activeModeTab = 'hybrid'"
          >
            <div class="flex items-center gap-2.5 mb-1.5">
              <div class="size-7 rounded-lg bg-purple-500/10 text-purple-600 flex items-center justify-center">
                <Icon name="lucide:git-merge" class="size-4" />
              </div>
              <h3 class="text-sm font-bold text-stone-900 dark:text-stone-100">Hybrid Approach</h3>
            </div>
            <p class="text-xs text-stone-600 dark:text-stone-400 leading-relaxed pl-9.5">
              Combine your creative seed with real-time market data to expand related angles that resonate with specific buyer communities.
            </p>
          </div>
        </div>

      </div>

    </div>
  </section>
</template>
