<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "~/stores/auth";
import Button from "~/components/ui/Button.vue";

const auth = useAuthStore();
const router = useRouter();
const isMobileMenuOpen = ref(false);

async function handleLogout() {
  try {
    isMobileMenuOpen.value = false;
    await auth.logout();
    router.push("/login");
  } catch (err) {
    console.error("Failed to log out:", err);
  }
}
</script>

<template>
  <header
    class="sticky top-0 z-40 w-full border-b border-border bg-white/95 backdrop-blur-md transition-all shadow-2xs"
    role="banner"
  >
    <div class="mx-auto flex max-w-6xl items-center justify-between px-3.5 sm:px-6 py-2.5 sm:py-3 gap-2">
      <div class="flex items-center gap-2 sm:gap-4 md:gap-8 min-w-0">
        <NuxtLink
          to="/"
          class="flex items-center gap-2 text-sm sm:text-base font-bold tracking-tight text-foreground hover:text-primary transition-colors group shrink-0"
          @click="isMobileMenuOpen = false"
        >
          <div class="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg bg-primary text-white shadow-2xs group-hover:bg-primary-hover transition-colors">
            <Icon name="lucide:store" class="size-3.5 sm:size-4" aria-hidden="true" />
          </div>
          <span class="inline font-bold">Marketplace Studio</span>
        </NuxtLink>

        <!-- Desktop Navigation -->
        <nav class="hidden md:flex items-center gap-1" role="navigation" aria-label="Main Navigation">
          <NuxtLink
            to="/"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
          >
            <Icon name="lucide:layout-dashboard" class="size-3.5" aria-hidden="true" />
            <span>Dashboard</span>
          </NuxtLink>
          <NuxtLink
            to="/library"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
            data-testid="nav-library-link"
          >
            <Icon name="lucide:images" class="size-3.5" aria-hidden="true" />
            <span>Mockup Library</span>
          </NuxtLink>
          <NuxtLink
            to="/settings"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
            data-testid="nav-settings-link"
          >
            <Icon name="lucide:settings" class="size-3.5" aria-hidden="true" />
            <span>Settings</span>
          </NuxtLink>
        </nav>
      </div>

      <!-- Right Header Actions (Desktop & Mobile) -->
      <div class="flex items-center gap-1.5 sm:gap-3 shrink-0">
        <div v-if="auth.user" class="hidden md:flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-3 py-1 text-xs text-secondary-foreground shadow-2xs">
          <Icon name="lucide:user" class="size-3.5 text-muted-foreground" aria-hidden="true" />
          <span class="font-medium truncate max-w-[140px]" data-testid="user-email">
            {{ auth.user.email }}
          </span>
        </div>

        <Button
          v-if="auth.user"
          variant="outline"
          size="sm"
          data-testid="logout-btn"
          class="hidden sm:inline-flex h-8 gap-1.5 px-2.5 text-xs font-medium text-secondary-foreground hover:bg-secondary hover:text-destructive transition-colors cursor-pointer"
          @click="handleLogout"
        >
          <Icon name="lucide:log-out" class="size-3.5" aria-hidden="true" />
          <span>Logout</span>
        </Button>

        <!-- Mobile Menu Hamburger Button -->
        <button
          type="button"
          class="md:hidden flex items-center justify-center size-8 rounded-lg border border-border bg-secondary/60 text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer"
          :aria-expanded="isMobileMenuOpen"
          aria-label="Toggle Navigation Menu"
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
        class="md:hidden border-t border-border bg-white px-4 py-3 space-y-2 shadow-md"
      >
        <NuxtLink
          to="/"
          class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
          active-class="bg-blue-50 text-primary font-bold border border-blue-200"
          @click="isMobileMenuOpen = false"
        >
          <Icon name="lucide:layout-dashboard" class="size-4 text-primary" aria-hidden="true" />
          <span>Dashboard</span>
        </NuxtLink>

        <NuxtLink
          to="/library"
          class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
          active-class="bg-blue-50 text-primary font-bold border border-blue-200"
          data-testid="nav-library-mobile-link"
          @click="isMobileMenuOpen = false"
        >
          <Icon name="lucide:images" class="size-4 text-primary" aria-hidden="true" />
          <span>Mockup Library</span>
        </NuxtLink>

        <NuxtLink
          to="/settings"
          class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
          active-class="bg-blue-50 text-primary font-bold border border-blue-200"
          data-testid="nav-settings-mobile-link"
          @click="isMobileMenuOpen = false"
        >
          <Icon name="lucide:settings" class="size-4 text-primary" aria-hidden="true" />
          <span>Settings</span>
        </NuxtLink>

        <div v-if="auth.user" class="pt-2 border-t border-border/80 flex items-center justify-between">
          <div class="flex items-center gap-2 text-xs text-muted-foreground min-w-0">
            <Icon name="lucide:user" class="size-3.5 shrink-0" aria-hidden="true" />
            <span class="truncate max-w-[160px]">{{ auth.user.email }}</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            class="h-7 text-xs px-2.5 text-destructive hover:bg-red-50 border-red-200 cursor-pointer"
            @click="handleLogout"
          >
            <Icon name="lucide:log-out" class="size-3 mr-1" aria-hidden="true" />
            <span>Logout</span>
          </Button>
        </div>
      </div>
    </transition>
  </header>
</template>
