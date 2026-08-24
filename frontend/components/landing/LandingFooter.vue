<script setup lang="ts">
import { useAuthStore } from "~/stores/auth";
import AppLogo from "~/components/AppLogo.vue";

const auth = useAuthStore();
const currentYear = new Date().getFullYear();
</script>

<template>
  <footer
    class="border-t border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] py-12"
    role="contentinfo"
  >
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 space-y-8">
      <div class="flex flex-col md:flex-row items-center justify-between gap-6">
        
        <!-- Brand / Identity -->
        <div class="flex items-center gap-3">
          <AppLogo sizeClass="size-7" />
          <span class="text-base font-extrabold tracking-tight text-stone-900 dark:text-stone-100">
            NovaCraft<span class="text-orange-600 dark:text-orange-500">Pixel</span>
          </span>
          <span class="text-xs text-stone-400 dark:text-stone-500 border-l border-stone-300 dark:border-stone-700 pl-3">
            Built for digital-product creators.
          </span>
        </div>

        <!-- Navigation Links -->
        <div class="flex flex-wrap items-center justify-center gap-6 text-xs font-medium text-stone-600 dark:text-stone-400">
          <a href="#how-it-works" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">How It Works</a>
          <a href="#discover" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">Discover</a>
          <a href="#mockups" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">Mockups</a>
          <a href="#listings" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">Listings</a>
          <a href="#safety" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">Safety & IP</a>
          <NuxtLink v-if="auth.isAuthenticated" to="/dashboard" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">
            Dashboard
          </NuxtLink>
          <NuxtLink v-else to="/login" class="hover:text-orange-600 dark:hover:text-orange-400 transition-colors">
            Sign In
          </NuxtLink>
        </div>

      </div>

      <div class="pt-6 border-t border-stone-200/60 dark:border-stone-800/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-stone-500 dark:text-stone-400">
        <p>© {{ currentYear }} NovaCraftPixel Studio. All rights reserved.</p>
        <p>Etsy is a trademark of Etsy, Inc. This application uses the Etsy API but is not endorsed or certified by Etsy, Inc.</p>
      </div>
    </div>
  </footer>
</template>
