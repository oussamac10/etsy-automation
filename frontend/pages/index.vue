<script setup lang="ts">
import LandingNavbar from "~/components/landing/LandingNavbar.vue";
import HeroSection from "~/components/landing/HeroSection.vue";
import ValueStrip from "~/components/landing/ValueStrip.vue";
import DiscoverSection from "~/components/landing/DiscoverSection.vue";
import ArtworkSection from "~/components/landing/ArtworkSection.vue";
import MockupShowcase from "~/components/landing/MockupShowcase.vue";
import ListingSection from "~/components/landing/ListingSection.vue";
import IpScreeningSection from "~/components/landing/IpScreeningSection.vue";
import EtsyDraftSection from "~/components/landing/EtsyDraftSection.vue";
import WorkflowTimeline from "~/components/landing/WorkflowTimeline.vue";
import ComparisonSection from "~/components/landing/ComparisonSection.vue";
import TrustControlSection from "~/components/landing/TrustControlSection.vue";
import FinalCta from "~/components/landing/FinalCta.vue";
import LandingFooter from "~/components/landing/LandingFooter.vue";

useHead({
  title: "NovaCraftPixel — Etsy Product Research, Artwork & Listing Workflow",
  htmlAttrs: { lang: "en" },
  meta: [
    {
      name: "description",
      content:
        "Discover Etsy product opportunities, create digital artwork, build mockups, optimize listing copy, screen key phrases, and prepare Etsy drafts from one workspace.",
    },
    { property: "og:title", content: "NovaCraftPixel — Etsy Product Research, Artwork & Listing Workflow" },
    {
      property: "og:description",
      content:
        "Discover Etsy product opportunities, create digital artwork, build mockups, optimize listing copy, screen key phrases, and prepare Etsy drafts from one workspace.",
    },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: "NovaCraftPixel — Etsy Product Research, Artwork & Listing Workflow" },
    {
      name: "twitter:description",
      content:
        "Discover Etsy product opportunities, create digital artwork, build mockups, optimize listing copy, screen key phrases, and prepare Etsy drafts from one workspace.",
    },
  ],
});
</script>

<template>
  <div class="min-h-screen bg-[#FAF9F5] dark:bg-[#0B0F17] text-stone-900 dark:text-stone-100 font-sans selection:bg-orange-500/20 selection:text-orange-900 dark:selection:text-orange-200">
    <!-- Sticky Navigation -->
    <LandingNavbar />

    <!-- Main Content Flow -->
    <main id="main" class="focus:outline-none">
      <!-- 1. Hero Section + Hero Mini-Demo Animation -->
      <HeroSection />

      <!-- 2. Value Strip -->
      <ValueStrip />

      <!-- 3. Discover Ideas Section -->
      <DiscoverSection />

      <!-- 4. Production Artwork Section -->
      <ArtworkSection />

      <!-- 5. Mockup Showcase -->
      <MockupShowcase />

      <!-- 6. Listing Optimization Section -->
      <ListingSection />

      <!-- 7. IP / Trademark Pre-Screen Section -->
      <IpScreeningSection />

      <!-- 8. Etsy Draft Section -->
      <EtsyDraftSection />

      <!-- 9. How It Works Timeline -->
      <WorkflowTimeline />

      <!-- 10. Before vs After Comparison -->
      <ComparisonSection />

      <!-- 11. Trust & Creator Control -->
      <TrustControlSection />

      <!-- 12. Final CTA Banner -->
      <FinalCta />
    </main>

    <!-- Footer -->
    <LandingFooter />
  </div>
</template>
