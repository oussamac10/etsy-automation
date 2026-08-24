<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";

const currentStep = ref(1);
const totalSteps = 7;
const isAutoPlaying = ref(true);
const prefersReducedMotion = ref(false);
const tabListRef = ref<HTMLElement | null>(null);

const steps = [
  { id: 1, label: "Market Signals", short: "Signals", icon: "lucide:trending-up" },
  { id: 2, label: "Opportunities", short: "Opps", icon: "lucide:search" },
  { id: 3, label: "Selected Idea", short: "Selected", icon: "lucide:sparkles" },
  { id: 4, label: "Artwork Master", short: "Artwork", icon: "lucide:image" },
  { id: 5, label: "Product Mockups", short: "Mockups", icon: "lucide:shirt" },
  { id: 6, label: "Listing Copy", short: "Listing", icon: "lucide:file-text" },
  { id: 7, label: "Etsy Draft Ready", short: "Draft Ready", icon: "lucide:check-circle-2" },
];

let timer: ReturnType<typeof setInterval> | null = null;

function scrollToActiveTab() {
  if (tabListRef.value && typeof window !== "undefined") {
    const container = tabListRef.value;
    const activeBtn = container.querySelector<HTMLElement>('button[aria-selected="true"]');
    if (activeBtn) {
      const btnLeft = activeBtn.offsetLeft;
      const btnWidth = activeBtn.offsetWidth;
      const containerWidth = container.clientWidth;
      const targetScrollLeft = btnLeft - containerWidth / 2 + btnWidth / 2;
      container.scrollTo({
        left: Math.max(0, targetScrollLeft),
        behavior: "smooth",
      });
    }
  }
}

watch(currentStep, async () => {
  await nextTick();
  scrollToActiveTab();
});

function setStep(step: number) {
  currentStep.value = step;
  if (isAutoPlaying.value) {
    restartLoop();
  }
}

function toggleAutoPlay() {
  isAutoPlaying.value = !isAutoPlaying.value;
  if (isAutoPlaying.value) {
    restartLoop();
  } else {
    stopLoop();
  }
}

function stopLoop() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function restartLoop() {
  stopLoop();
  if (prefersReducedMotion.value || !isAutoPlaying.value) return;
  timer = setInterval(() => {
    if (isAutoPlaying.value && !prefersReducedMotion.value) {
      currentStep.value = currentStep.value >= totalSteps ? 1 : currentStep.value + 1;
    }
  }, 2200);
}

onMounted(() => {
  if (typeof window !== "undefined") {
    const motionQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
    prefersReducedMotion.value = motionQuery?.matches ?? false;

    if (prefersReducedMotion.value) {
      currentStep.value = totalSteps; // show complete state
      return;
    }

    restartLoop();

    if (motionQuery?.addEventListener) {
      motionQuery.addEventListener("change", (e) => {
        prefersReducedMotion.value = e.matches;
        if (e.matches) {
          stopLoop();
          currentStep.value = totalSteps;
        } else {
          restartLoop();
        }
      });
    }
  }
});

onUnmounted(() => {
  stopLoop();
});
</script>

<template>
  <div
    class="w-full max-w-4xl mx-auto rounded-2xl border border-stone-200/90 dark:border-stone-800 bg-white/90 dark:bg-stone-900/90 shadow-xl overflow-hidden backdrop-blur-md"
    data-testid="hero-workflow-demo"
  >
    <!-- Top Window Chrome Header -->
    <div class="flex items-center justify-between px-4 sm:px-6 py-2.5 sm:py-3 border-b border-stone-200/80 dark:border-stone-800 bg-stone-50/95 dark:bg-stone-950/70">
      <!-- Left: Mac Window Dots & Live Studio Badge -->
      <div class="flex items-center gap-2.5 sm:gap-3">
        <div class="flex items-center gap-1.5" aria-hidden="true">
          <div class="size-2.5 sm:size-3 rounded-full bg-red-500/80 border border-red-600/30 shadow-2xs" />
          <div class="size-2.5 sm:size-3 rounded-full bg-amber-500/80 border border-amber-600/30 shadow-2xs" />
          <div class="size-2.5 sm:size-3 rounded-full bg-emerald-500/80 border border-emerald-600/30 shadow-2xs" />
        </div>
        <div class="h-3.5 w-px bg-stone-300 dark:bg-stone-700 mx-0.5" aria-hidden="true" />
        <div class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-[10px] sm:text-[11px] font-bold shadow-2xs">
          <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Live Studio Workflow Demo</span>
        </div>
      </div>

      <!-- Right: Play / Pause Control Button -->
      <button
        type="button"
        class="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-lg text-[11px] sm:text-xs font-bold text-stone-600 dark:text-stone-300 hover:text-orange-600 dark:hover:text-orange-400 bg-white dark:bg-stone-800 hover:bg-stone-100 dark:hover:bg-stone-700 border border-stone-200/80 dark:border-stone-700/80 transition-colors cursor-pointer shadow-2xs"
        :aria-label="isAutoPlaying ? 'Pause auto-play' : 'Resume auto-play'"
        @click="toggleAutoPlay"
      >
        <Icon :name="isAutoPlaying ? 'lucide:pause' : 'lucide:play'" class="size-3 text-orange-600 dark:text-orange-400" aria-hidden="true" />
        <span>{{ isAutoPlaying ? 'Pause Demo' : 'Resume Demo' }}</span>
      </button>
    </div>

    <!-- Dedicated Full-Width Segmented Tab Navigation Bar -->
    <div class="px-3 sm:px-5 py-2 border-b border-stone-200/80 dark:border-stone-800 bg-stone-100/50 dark:bg-stone-900/50">
      <div
        ref="tabListRef"
        class="flex items-center gap-1 overflow-x-auto scroll-smooth scrollbar-none w-full max-w-full touch-pan-x p-1 rounded-xl bg-stone-200/60 dark:bg-stone-950 border border-stone-300/50 dark:border-stone-800"
        role="tablist"
        aria-label="Workflow Demo Steps"
      >
        <button
          v-for="step in steps"
          :key="step.id"
          type="button"
          role="tab"
          :aria-selected="currentStep === step.id"
          :class="[
            'flex-1 min-w-fit px-2.5 sm:px-3 py-1.5 rounded-lg text-[11px] sm:text-xs font-bold transition-all duration-150 cursor-pointer flex items-center justify-center gap-1.5 shrink-0 whitespace-nowrap',
            currentStep === step.id
              ? 'bg-orange-600 text-white shadow-sm'
              : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 hover:bg-white/50 dark:hover:bg-stone-800/50',
          ]"
          @click="setStep(step.id)"
        >
          <span
            :class="[
              'size-4 rounded-full text-[10px] font-black flex items-center justify-center shrink-0',
              currentStep === step.id
                ? 'bg-white/20 text-white'
                : 'bg-stone-300/80 dark:bg-stone-800 text-stone-600 dark:text-stone-400',
            ]"
          >
            {{ step.id }}
          </span>
          <span class="hidden md:inline">{{ step.label }}</span>
          <span class="md:hidden">{{ step.short }}</span>
        </button>
      </div>
    </div>

    <!-- Main Dynamic Demo Canvas -->
    <div class="relative min-h-[360px] sm:min-h-[400px] p-4 sm:p-8 flex flex-col justify-center bg-gradient-to-b from-[#FFFDF9]/40 to-stone-50/40 dark:from-stone-900/20 dark:to-stone-950/40">
      
      <!-- STEP 1: Market Signals -->
      <div
        v-if="currentStep === 1"
        class="space-y-4 animate-in fade-in zoom-in-95 duration-300"
        data-testid="demo-step-1"
      >
        <div class="text-center max-w-md mx-auto mb-6">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
            <Icon name="lucide:radio" class="size-3.5 animate-pulse" />
            Step 1: Real-Time Demand Signals
          </span>
          <h4 class="mt-2 text-lg sm:text-xl font-bold text-stone-900 dark:text-stone-100">Scanning Etsy Market Intent</h4>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 max-w-2xl mx-auto">
          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3 sm:p-4 text-center shadow-xs">
            <div class="flex items-center justify-center size-9 mx-auto rounded-lg bg-blue-500/10 text-blue-600 mb-2">
              <Icon name="lucide:search" class="size-4" />
            </div>
            <p class="text-xs text-stone-500 dark:text-stone-400">Search Demand</p>
            <p class="text-sm sm:text-base font-bold text-stone-900 dark:text-stone-100 mt-0.5">High Intent</p>
          </div>

          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3 sm:p-4 text-center shadow-xs">
            <div class="flex items-center justify-center size-9 mx-auto rounded-lg bg-emerald-500/10 text-emerald-600 mb-2">
              <Icon name="lucide:trending-up" class="size-4" />
            </div>
            <p class="text-xs text-stone-500 dark:text-stone-400">Trend Trajectory</p>
            <p class="text-sm sm:text-base font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">+48% Rising</p>
          </div>

          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3 sm:p-4 text-center shadow-xs">
            <div class="flex items-center justify-center size-9 mx-auto rounded-lg bg-amber-500/10 text-amber-600 mb-2">
              <Icon name="lucide:users" class="size-4" />
            </div>
            <p class="text-xs text-stone-500 dark:text-stone-400">Competition</p>
            <p class="text-sm sm:text-base font-bold text-stone-900 dark:text-stone-100 mt-0.5">Medium Gap</p>
          </div>

          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3 sm:p-4 text-center shadow-xs">
            <div class="flex items-center justify-center size-9 mx-auto rounded-lg bg-purple-500/10 text-purple-600 mb-2">
              <Icon name="lucide:calendar-clock" class="size-4" />
            </div>
            <p class="text-xs text-stone-500 dark:text-stone-400">Seasonal Window</p>
            <p class="text-sm sm:text-base font-bold text-purple-600 dark:text-purple-400 mt-0.5">Sell Now</p>
          </div>
        </div>
      </div>

      <!-- STEP 2: 3 Opportunity Cards -->
      <div
        v-if="currentStep === 2"
        class="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
        data-testid="demo-step-2"
      >
        <div class="text-center max-w-md mx-auto mb-4">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold">
            <Icon name="lucide:list-checks" class="size-3.5" />
            Step 2: Synthesizing Top Opportunities
          </span>
          <h4 class="mt-1.5 text-lg sm:text-xl font-bold text-stone-900 dark:text-stone-100">3 Scored Market Concepts</h4>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 max-w-3xl mx-auto">
          <!-- Card 1 -->
          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3.5 shadow-xs opacity-85">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500">Option 1</span>
              <span class="text-xs font-bold text-stone-700 dark:text-stone-300">74/100</span>
            </div>
            <p class="font-bold text-xs sm:text-sm text-stone-800 dark:text-stone-200">Vintage Coffee Cat</p>
            <p class="text-[11px] text-stone-500 mt-1">Cozy cafe niche, steady demand</p>
          </div>

          <!-- Card 2 (Top) -->
          <div class="rounded-xl border-2 border-orange-500 bg-orange-50/40 dark:bg-orange-950/20 p-3.5 shadow-md transform sm:scale-105">
            <div class="flex items-center justify-between mb-1.5">
              <span class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-extrabold uppercase bg-orange-600 text-white">Top Match</span>
              <span class="text-xs font-extrabold text-orange-600 dark:text-orange-400">89/100</span>
            </div>
            <p class="font-bold text-xs sm:text-sm text-stone-900 dark:text-stone-100">Retro Radiology Halloween</p>
            <p class="text-[11px] text-stone-600 dark:text-stone-400 mt-1">High seasonal surge, nurse & tech audience</p>
          </div>

          <!-- Card 3 -->
          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3.5 shadow-xs opacity-85">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[10px] font-bold uppercase tracking-wider text-stone-500">Option 3</span>
              <span class="text-xs font-bold text-stone-700 dark:text-stone-300">68/100</span>
            </div>
            <p class="font-bold text-xs sm:text-sm text-stone-800 dark:text-stone-200">Botanical Plant Mom</p>
            <p class="text-[11px] text-stone-500 mt-1">Evergreen aesthetic, high competition</p>
          </div>
        </div>
      </div>

      <!-- STEP 3: Opportunity Selected Detail -->
      <div
        v-if="currentStep === 3"
        class="space-y-4 animate-in fade-in zoom-in-95 duration-300"
        data-testid="demo-step-3"
      >
        <div class="max-w-xl mx-auto rounded-xl border border-orange-500/40 bg-white dark:bg-stone-900 p-4 sm:p-6 shadow-md">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-stone-100 dark:border-stone-800 pb-3">
            <div>
              <span class="text-[10px] font-extrabold uppercase tracking-wider text-orange-600 dark:text-orange-400">Selected Opportunity</span>
              <h4 class="text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">Retro Radiology Halloween</h4>
            </div>
            <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-100 dark:bg-orange-950/50 text-orange-700 dark:text-orange-300 text-xs font-extrabold">
              <Icon name="lucide:award" class="size-3.5" />
              <span>Score: 89/100</span>
            </div>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 text-xs">
            <div class="rounded-lg bg-stone-50 dark:bg-stone-800/60 p-2 text-center">
              <span class="text-stone-500 block text-[10px]">Trend</span>
              <span class="font-bold text-emerald-600 dark:text-emerald-400">Rising Fast</span>
            </div>
            <div class="rounded-lg bg-stone-50 dark:bg-stone-800/60 p-2 text-center">
              <span class="text-stone-500 block text-[10px]">Competition</span>
              <span class="font-bold text-stone-800 dark:text-stone-200">Medium</span>
            </div>
            <div class="rounded-lg bg-stone-50 dark:bg-stone-800/60 p-2 text-center">
              <span class="text-stone-500 block text-[10px]">Timing</span>
              <span class="font-bold text-orange-600">Sell Now</span>
            </div>
            <div class="rounded-lg bg-stone-50 dark:bg-stone-800/60 p-2 text-center">
              <span class="text-stone-500 block text-[10px]">IP Risk</span>
              <span class="font-bold text-emerald-600">Low Flag</span>
            </div>
          </div>

          <div class="mt-3 p-2.5 rounded-lg bg-orange-50/60 dark:bg-orange-950/20 text-xs text-stone-700 dark:text-stone-300">
            <span class="font-bold text-orange-700 dark:text-orange-400">Why this could sell:</span>
            "Combines seasonal Halloween urgency with professional pride for X-ray techs, radiologists, and healthcare staff."
          </div>
        </div>
      </div>

      <!-- STEP 4: Transparent Artwork Preview -->
      <div
        v-if="currentStep === 4"
        class="space-y-4 animate-in fade-in duration-300"
        data-testid="demo-step-4"
      >
        <div class="text-center mb-3">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-xs font-semibold">
            <Icon name="lucide:image" class="size-3.5" />
            Step 4: Master 300 DPI Transparent PNG
          </span>
          <h4 class="mt-1 text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">Production-Ready Asset Generated</h4>
        </div>

        <div class="flex items-center justify-center">
          <div class="relative size-48 sm:size-56 rounded-2xl border border-stone-300 dark:border-stone-700 overflow-hidden shadow-inner flex items-center justify-center bg-alpha-grid bg-stone-100/90 dark:bg-stone-900/90">
            <!-- Graphic Representation -->
            <div class="relative z-10 text-center p-3 filter drop-shadow-md">
              <div class="size-16 sm:size-20 mx-auto flex items-center justify-center text-orange-500">
                <Icon name="lucide:sparkles" class="size-14 sm:size-16 text-orange-500 animate-spin-slow filter drop-shadow-sm" />
              </div>
              <p class="mt-2 text-xs font-extrabold tracking-wide text-stone-900 dark:text-stone-100 uppercase">Retro Skeleton Coffee</p>
              <span class="inline-block text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full mt-1">
                Alpha Channel Verified ✓
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- STEP 5: Product Mockups -->
      <div
        v-if="currentStep === 5"
        class="space-y-4 animate-in fade-in duration-300"
        data-testid="demo-step-5"
      >
        <div class="text-center mb-3">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 text-xs font-semibold">
            <Icon name="lucide:shirt" class="size-3.5" />
            Step 5: Automated Mockup Generation
          </span>
          <h4 class="mt-1 text-base sm:text-lg font-bold text-stone-900 dark:text-stone-100">Rendered Across Creator Products</h4>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4 max-w-2xl mx-auto">
          <!-- T-Shirt Mockup -->
          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-100/60 dark:bg-stone-900/60 p-3 text-center shadow-xs flex flex-col items-center">
            <div class="size-20 sm:size-24 rounded-lg bg-stone-200 dark:bg-stone-800 flex items-center justify-center relative overflow-hidden mb-2">
              <Icon name="lucide:shirt" class="size-12 text-stone-400" />
              <div class="absolute inset-0 flex items-center justify-center">
                <span class="size-8 rounded-full bg-orange-500/80 flex items-center justify-center text-[8px] font-bold text-white shadow-xs">ART</span>
              </div>
            </div>
            <span class="text-xs font-bold text-stone-800 dark:text-stone-200">Graphic T-Shirt</span>
          </div>

          <!-- Ceramic Mug Mockup -->
          <div class="rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-100/60 dark:bg-stone-900/60 p-3 text-center shadow-xs flex flex-col items-center">
            <div class="size-20 sm:size-24 rounded-lg bg-stone-200 dark:bg-stone-800 flex items-center justify-center relative overflow-hidden mb-2">
              <Icon name="lucide:coffee" class="size-12 text-stone-400" />
              <div class="absolute inset-0 flex items-center justify-center">
                <span class="size-7 rounded-full bg-orange-500/80 flex items-center justify-center text-[7px] font-bold text-white shadow-xs">ART</span>
              </div>
            </div>
            <span class="text-xs font-bold text-stone-800 dark:text-stone-200">Ceramic Mug (11oz)</span>
          </div>

          <!-- Tote Bag Mockup -->
          <div class="hidden sm:flex rounded-xl border border-stone-200 dark:border-stone-800 bg-stone-100/60 dark:bg-stone-900/60 p-3 text-center shadow-xs flex-col items-center">
            <div class="size-20 sm:size-24 rounded-lg bg-stone-200 dark:bg-stone-800 flex items-center justify-center relative overflow-hidden mb-2">
              <Icon name="lucide:shopping-bag" class="size-12 text-stone-400" />
              <div class="absolute inset-0 flex items-center justify-center">
                <span class="size-8 rounded-full bg-orange-500/80 flex items-center justify-center text-[8px] font-bold text-white shadow-xs">ART</span>
              </div>
            </div>
            <span class="text-xs font-bold text-stone-800 dark:text-stone-200">Canvas Tote Bag</span>
          </div>
        </div>
      </div>

      <!-- STEP 6: Listing Optimization -->
      <div
        v-if="currentStep === 6"
        class="space-y-3 animate-in fade-in duration-300"
        data-testid="demo-step-6"
      >
        <div class="text-center mb-2">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
            <Icon name="lucide:tags" class="size-3.5" />
            Step 6: SEO Title, Summary & 13 Tags
          </span>
        </div>

        <div class="max-w-xl mx-auto rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-4 shadow-sm space-y-2.5 text-xs">
          <div>
            <span class="text-[10px] font-bold uppercase text-stone-500">Optimized Title</span>
            <p class="font-bold text-stone-900 dark:text-stone-100 text-xs sm:text-sm">
              Retro Radiology Skeleton PNG · Halloween X-Ray Tech Sublimation Design · Spooky Nurse Shirt Digital Download
            </p>
          </div>

          <div>
            <span class="text-[10px] font-bold uppercase text-stone-500">13 Etsy Tags Generated</span>
            <div class="flex flex-wrap gap-1 mt-1">
              <span v-for="tag in ['radiology tech', 'halloween png', 'xray skeleton', 'spooky nurse', 'retro healthcare', 'sublimation file', 'dtg print']" :key="tag" class="px-2 py-0.5 rounded bg-stone-100 dark:bg-stone-800 text-[10px] font-medium text-stone-700 dark:text-stone-300">
                #{{ tag }}
              </span>
              <span class="px-2 py-0.5 rounded bg-orange-100 dark:bg-orange-950/60 text-[10px] font-bold text-orange-700 dark:text-orange-300">+6 more tags</span>
            </div>
          </div>
        </div>
      </div>

      <!-- STEP 7: Etsy Draft Ready -->
      <div
        v-if="currentStep === 7"
        class="space-y-4 text-center animate-in fade-in zoom-in-95 duration-300"
        data-testid="demo-step-7"
      >
        <div class="size-14 sm:size-16 mx-auto rounded-full bg-emerald-500/10 text-emerald-600 flex items-center justify-center shadow-sm">
          <Icon name="lucide:check-circle-2" class="size-8 sm:size-10" />
        </div>

        <div class="max-w-md mx-auto space-y-1">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-xs font-extrabold">
            Etsy Draft Ready ✓
          </span>
          <h4 class="text-lg sm:text-xl font-extrabold text-stone-900 dark:text-stone-100">Ready for Creator Review</h4>
          <p class="text-xs sm:text-sm text-stone-600 dark:text-stone-400">
            All assets, mockups, and SEO copy are prepared as a safe Etsy shop draft. You review and publish manually on Etsy.
          </p>
        </div>

        <div class="pt-1">
          <NuxtLink
            to="/register"
            class="inline-flex items-center gap-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 text-white px-5 py-2.5 text-xs sm:text-sm font-bold shadow-md cursor-pointer transition-all"
          >
            <span>Start Your First Workflow</span>
            <Icon name="lucide:arrow-right" class="size-4" />
          </NuxtLink>
        </div>
      </div>

    </div>

    <!-- Bottom Progress Track -->
    <div class="h-1.5 w-full bg-stone-100 dark:bg-stone-800">
      <div
        class="h-full bg-orange-600 transition-all duration-300"
        :style="{ width: `${(currentStep / totalSteps) * 100}%` }"
      />
    </div>
  </div>
</template>
