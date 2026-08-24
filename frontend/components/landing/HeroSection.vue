<script setup lang="ts">
import { useAuthStore } from "~/stores/auth";
import HeroWorkflowDemo from "~/components/landing/HeroWorkflowDemo.vue";

const auth = useAuthStore();

const trustPillars = [
  { label: "Market Research", icon: "lucide:trending-up" },
  { label: "Artwork Generation", icon: "lucide:wand-sparkles" },
  { label: "Product Mockups", icon: "lucide:shirt" },
  { label: "Listing SEO", icon: "lucide:tags" },
  { label: "IP Pre-Screen", icon: "lucide:shield-check" },
  { label: "Etsy Drafts", icon: "lucide:store" },
];
</script>

<template>
  <section
    class="relative pt-8 pb-16 sm:pt-14 sm:pb-24 overflow-hidden"
    aria-labelledby="hero-heading"
  >
    <!-- Background Warm Gradient Circles (Decorative) -->
    <div class="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden" aria-hidden="true">
      <div class="absolute -top-24 size-[550px] rounded-full bg-orange-400/10 dark:bg-orange-500/10 blur-3xl animate-pulse-soft" />
      <div class="absolute top-1/2 -right-24 size-[450px] rounded-full bg-amber-400/10 dark:bg-amber-500/10 blur-3xl animate-pulse-soft" style="animation-delay: 2s;" />
      <div class="absolute -bottom-24 -left-24 size-[450px] rounded-full bg-orange-500/5 blur-3xl animate-pulse-soft" style="animation-delay: 4s;" />
    </div>

    <!-- Floating Decorative Badges (Desktop) -->
    <div class="hidden xl:block absolute left-8 top-32 pointer-events-none animate-float-slow z-10" aria-hidden="true">
      <div class="inline-flex items-center gap-2 rounded-2xl border border-stone-200/80 dark:border-stone-800 bg-white/90 dark:bg-stone-900/90 p-3 shadow-lg backdrop-blur-md">
        <div class="size-8 rounded-xl bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center">
          <Icon name="lucide:sparkles" class="size-4" />
        </div>
        <div class="text-left">
          <p class="text-[10px] font-bold text-stone-400 uppercase tracking-wider">Opportunity Score</p>
          <p class="text-xs font-black text-stone-900 dark:text-stone-100">89/100 High Demand</p>
        </div>
      </div>
    </div>

    <div class="hidden xl:block absolute right-8 top-36 pointer-events-none animate-float-reverse z-10" aria-hidden="true">
      <div class="inline-flex items-center gap-2 rounded-2xl border border-stone-200/80 dark:border-stone-800 bg-white/90 dark:bg-stone-900/90 p-3 shadow-lg backdrop-blur-md">
        <div class="size-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
          <Icon name="lucide:shield-check" class="size-4" />
        </div>
        <div class="text-left">
          <p class="text-[10px] font-bold text-stone-400 uppercase tracking-wider">Draft Guarantee</p>
          <p class="text-xs font-black text-stone-900 dark:text-stone-100">Zero Auto-Publish</p>
        </div>
      </div>
    </div>

    <div class="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 text-center space-y-8 sm:space-y-12">
      <!-- Top Announcement Badge -->
      <div class="inline-flex items-center gap-2 rounded-full border border-orange-500/30 bg-orange-500/10 px-3.5 py-1 text-xs font-semibold text-orange-700 dark:text-orange-300 backdrop-blur-xs shadow-2xs hover:scale-105 transition-transform duration-300">
        <span class="size-2 rounded-full bg-orange-500 animate-pulse-ring" />
        <span>End-to-End Creator Workspace</span>
      </div>

      <!-- Main Headline & Subheadline -->
      <div class="max-w-4xl mx-auto space-y-4 sm:space-y-6">
        <h1
          id="hero-heading"
          class="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-stone-900 dark:text-stone-100 leading-[1.15] sm:leading-[1.12]"
        >
          Turn Etsy opportunities into <span class="text-orange-600 dark:text-orange-500 bg-gradient-to-r from-orange-600 via-amber-500 to-orange-600 bg-clip-text text-transparent">ready-to-list</span> digital products.
        </h1>

        <p class="mx-auto max-w-2xl text-base sm:text-lg lg:text-xl text-stone-600 dark:text-stone-300 font-normal leading-relaxed">
          Research demand, create artwork, build product mockups, optimize your listing, screen key phrases, and prepare your Etsy draft from one workspace.
        </p>
      </div>

      <!-- CTAs & Action Area -->
      <div class="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 pt-2">
        <template v-if="auth.isAuthenticated">
          <NuxtLink
            to="/dashboard"
            data-testid="hero-primary-cta"
            class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-7 py-3.5 text-base font-bold shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer"
          >
            <Icon name="lucide:layout-dashboard" class="size-5" aria-hidden="true" />
            <span>Open Dashboard</span>
          </NuxtLink>
        </template>
        <template v-else>
          <NuxtLink
            to="/register"
            data-testid="hero-primary-cta"
            class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-7 py-3.5 text-base font-bold shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer group"
          >
            <span>Start Creating</span>
            <Icon name="lucide:arrow-right" class="size-5 transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true" />
          </NuxtLink>
        </template>

        <a
          href="#how-it-works"
          class="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-stone-300 dark:border-stone-700 bg-white/80 dark:bg-stone-900/80 hover:bg-stone-100 dark:hover:bg-stone-800 text-stone-800 dark:text-stone-200 px-6 py-3.5 text-base font-semibold hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer backdrop-blur-xs"
        >
          <Icon name="lucide:play-circle" class="size-5 text-stone-500 dark:text-stone-400" aria-hidden="true" />
          <span>See How It Works</span>
        </a>
      </div>

      <!-- Trust Pillars Row -->
      <div class="pt-4 border-t border-stone-200/60 dark:border-stone-800/60">
        <p class="text-xs font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400 mb-3">
          Complete Human-in-the-Loop Workflow
        </p>
        <div class="flex flex-wrap items-center justify-center gap-2 sm:gap-4">
          <div
            v-for="pillar in trustPillars"
            :key="pillar.label"
            class="inline-flex items-center gap-1.5 rounded-lg border border-stone-200/70 dark:border-stone-800/80 bg-white/60 dark:bg-stone-900/60 px-3 py-1.5 text-xs font-medium text-stone-700 dark:text-stone-300 shadow-2xs backdrop-blur-xs hover:border-orange-500/40 hover:bg-white dark:hover:bg-stone-900 hover:scale-105 transition-all duration-200"
          >
            <Icon :name="pillar.icon" class="size-3.5 text-orange-600 dark:text-orange-500" aria-hidden="true" />
            <span>{{ pillar.label }}</span>
          </div>
        </div>
      </div>

      <!-- Interactive Product Demo Animation Canvas -->
      <div class="pt-6 sm:pt-10">
        <HeroWorkflowDemo />
      </div>
    </div>
  </section>
</template>
