<script setup lang="ts">
import { useAuthStore } from "~/stores/auth";
import { useScrollReveal } from "~/composables/useScrollReveal";

const auth = useAuthStore();
const { targetRef, isVisible } = useScrollReveal();
</script>

<template>
  <section
    ref="targetRef"
    class="py-16 sm:py-24 border-b border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] relative overflow-hidden"
    aria-labelledby="final-cta-heading"
  >
    <!-- Background Warm Circles -->
    <div class="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden" aria-hidden="true">
      <div class="size-[500px] rounded-full bg-orange-500/10 dark:bg-orange-500/15 blur-3xl animate-pulse-soft" />
    </div>

    <div class="relative mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center space-y-8">
      
      <div
        class="space-y-4 transition-all duration-700"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 text-xs font-semibold shadow-2xs hover:scale-105 transition-transform duration-200">
          <Icon name="lucide:sparkles" class="size-3.5 animate-spin-slow" aria-hidden="true" />
          Get Started in Minutes
        </span>

        <h2
          id="final-cta-heading"
          class="text-3xl sm:text-5xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100 leading-tight"
        >
          Ready to find your next <span class="text-orange-600 dark:text-orange-500 bg-gradient-to-r from-orange-600 via-amber-500 to-orange-600 bg-clip-text text-transparent">Etsy product</span> opportunity?
        </h2>

        <p class="mx-auto max-w-xl text-base sm:text-lg text-stone-600 dark:text-stone-300 leading-relaxed">
          Research demand, create artwork, build mockups, and prepare verified Etsy drafts from one workspace.
        </p>
      </div>

      <div
        class="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 transition-all duration-700 delay-100"
        :class="[isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6']"
      >
        <template v-if="auth.isAuthenticated">
          <NuxtLink
            to="/dashboard"
            data-testid="final-cta-primary"
            class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-8 py-4 text-base font-bold shadow-md hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer"
          >
            <Icon name="lucide:layout-dashboard" class="size-5" aria-hidden="true" />
            <span>Open Dashboard</span>
          </NuxtLink>
        </template>
        <template v-else>
          <NuxtLink
            to="/register"
            data-testid="final-cta-primary"
            class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-8 py-4 text-base font-bold shadow-md hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer group"
          >
            <span>Start Creating Now</span>
            <Icon name="lucide:arrow-right" class="size-5 transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true" />
          </NuxtLink>

          <NuxtLink
            to="/login"
            data-testid="final-cta-secondary"
            class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-orange-500/40 hover:bg-orange-500/10 text-orange-600 dark:text-orange-400 bg-white/80 dark:bg-stone-900/80 hover:-translate-y-0.5 active:translate-y-0 px-7 py-4 text-base font-semibold transition-all duration-200 cursor-pointer backdrop-blur-xs shadow-2xs"
          >
            <span>Sign In</span>
          </NuxtLink>
        </template>
      </div>

    </div>
  </section>
</template>
