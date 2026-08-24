<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useAuthStore } from "~/stores/auth";
import AppLogo from "~/components/AppLogo.vue";
import ThemeToggle from "~/components/ThemeToggle.vue";

const auth = useAuthStore();
const isScrolled = ref(false);
const isMobileMenuOpen = ref(false);

function handleScroll() {
  if (typeof window !== "undefined") {
    const scrolled = window.scrollY > 20;
    if (isScrolled.value !== scrolled) {
      isScrolled.value = scrolled;
    }
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
  }
});

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("scroll", handleScroll);
  }
});

const navLinks = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Discover", href: "#discover" },
  { label: "Mockups", href: "#mockups" },
  { label: "Listings", href: "#listings" },
  { label: "Safety", href: "#safety" },
];

function closeMobileMenu() {
  isMobileMenuOpen.value = false;
}

function scrollToSection(e: MouseEvent, href: string) {
  if (href.startsWith("#") && typeof document !== "undefined") {
    e.preventDefault();
    const targetId = href.slice(1);
    const targetEl = document.getElementById(targetId);
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
      if (typeof window !== "undefined" && window.history?.pushState) {
        window.history.pushState(null, "", href);
      }
      closeMobileMenu();
    }
  }
}
</script>

<template>
  <header
    class="sticky top-0 z-50 w-full transition-all duration-200"
    :class="[
      isScrolled
        ? 'bg-[#FAF9F5]/95 dark:bg-[#0B0F17]/95 backdrop-blur-md border-b border-stone-200/80 dark:border-stone-800 shadow-2xs py-2.5 sm:py-3'
        : 'bg-transparent border-b border-transparent py-3.5 sm:py-4',
    ]"
    role="banner"
  >
    <div class="mx-auto flex max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
      <!-- Brand Logo -->
      <NuxtLink
        to="/"
        class="flex items-center gap-2.5 text-base sm:text-lg font-bold tracking-tight text-stone-900 dark:text-stone-100 hover:opacity-90 transition-opacity group shrink-0"
        aria-label="NovaCraftPixel Home"
      >
        <AppLogo sizeClass="size-7 sm:size-8" />
        <span class="font-extrabold tracking-tight">NovaCraft<span class="text-orange-600 dark:text-orange-500">Pixel</span></span>
      </NuxtLink>

      <!-- Desktop Nav Links -->
      <nav class="hidden md:flex items-center gap-6 lg:gap-8" role="navigation" aria-label="Main Navigation">
        <a
          v-for="link in navLinks"
          :key="link.href"
          :href="link.href"
          class="text-xs lg:text-sm font-medium text-stone-600 dark:text-stone-300 hover:text-orange-600 dark:hover:text-orange-400 transition-colors cursor-pointer"
          @click="scrollToSection($event, link.href)"
        >
          {{ link.label }}
        </a>
      </nav>

      <!-- Right Header Actions -->
      <div class="flex items-center gap-2 sm:gap-3 shrink-0">
        <ThemeToggle />

        <!-- Authenticated visitor -->
        <template v-if="auth.isAuthenticated">
          <NuxtLink
            to="/dashboard"
            data-testid="landing-nav-dashboard-link"
            class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-3.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-semibold shadow-xs hover:shadow-sm transition-all cursor-pointer"
          >
            <Icon name="lucide:layout-dashboard" class="size-3.5 sm:size-4" aria-hidden="true" />
            <span>Open Dashboard</span>
          </NuxtLink>
        </template>

        <!-- Unauthenticated visitor -->
        <template v-else>
          <NuxtLink
            to="/login"
            data-testid="landing-nav-login-link"
            class="hidden sm:inline-flex items-center justify-center rounded-lg border border-orange-500/40 hover:bg-orange-500/10 text-orange-600 dark:text-orange-400 px-3.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-semibold transition-all cursor-pointer"
          >
            Sign In
          </NuxtLink>

          <NuxtLink
            to="/register"
            data-testid="landing-nav-register-link"
            class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white px-3.5 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-semibold shadow-xs hover:shadow-sm transition-all cursor-pointer"
          >
            <span>Start Creating</span>
            <Icon name="lucide:arrow-right" class="size-3.5 sm:size-4" aria-hidden="true" />
          </NuxtLink>
        </template>

        <!-- Mobile Menu Hamburger Button -->
        <button
          type="button"
          class="md:hidden flex items-center justify-center size-9 rounded-lg border border-stone-200 dark:border-stone-800 bg-stone-100/80 dark:bg-stone-900/80 text-stone-700 dark:text-stone-300 hover:text-stone-900 dark:hover:text-stone-100 transition-colors cursor-pointer"
          :aria-expanded="isMobileMenuOpen"
          aria-label="Toggle Navigation Menu"
          data-testid="mobile-menu-toggle"
          @click="isMobileMenuOpen = !isMobileMenuOpen"
        >
          <Icon v-if="isMobileMenuOpen" name="lucide:x" class="size-4" aria-hidden="true" />
          <Icon v-else name="lucide:menu" class="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>

    <!-- Mobile Dropdown Navigation Drawer -->
    <transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="isMobileMenuOpen"
        class="md:hidden border-t border-stone-200/80 dark:border-stone-800 bg-[#FAF9F5] dark:bg-[#0B0F17] px-4 py-4 space-y-3 shadow-lg"
        data-testid="mobile-menu-drawer"
      >
        <div class="flex flex-col space-y-2">
          <a
            v-for="link in navLinks"
            :key="link.href"
            :href="link.href"
            class="flex items-center px-3 py-2 rounded-lg text-sm font-medium text-stone-700 dark:text-stone-300 hover:bg-stone-200/50 dark:hover:bg-stone-800/50 hover:text-orange-600 dark:hover:text-orange-400 transition-colors cursor-pointer"
            @click="scrollToSection($event, link.href)"
          >
            {{ link.label }}
          </a>
        </div>

        <div class="pt-3 border-t border-stone-200 dark:border-stone-800 flex flex-col gap-2">
          <template v-if="auth.isAuthenticated">
            <NuxtLink
              to="/dashboard"
              class="w-full flex items-center justify-center gap-1.5 rounded-lg bg-orange-600 text-white px-4 py-2.5 text-sm font-semibold shadow-xs cursor-pointer"
              @click="closeMobileMenu"
            >
              <Icon name="lucide:layout-dashboard" class="size-4" aria-hidden="true" />
              <span>Open Dashboard</span>
            </NuxtLink>
          </template>
          <template v-else>
            <NuxtLink
              to="/login"
              class="w-full flex items-center justify-center rounded-lg border border-orange-500/40 hover:bg-orange-500/10 text-orange-600 dark:text-orange-400 px-4 py-2.5 text-sm font-semibold transition-colors"
              @click="closeMobileMenu"
            >
              Sign In
            </NuxtLink>
            <NuxtLink
              to="/register"
              class="w-full flex items-center justify-center gap-1.5 rounded-lg bg-orange-600 text-white px-4 py-2.5 text-sm font-semibold shadow-xs cursor-pointer"
              @click="closeMobileMenu"
            >
              <span>Start Creating</span>
              <Icon name="lucide:arrow-right" class="size-4" aria-hidden="true" />
            </NuxtLink>
          </template>
        </div>
      </div>
    </transition>
  </header>
</template>
