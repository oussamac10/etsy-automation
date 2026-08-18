<script setup lang="ts">
import { useAuthStore } from "~/stores/auth";
import Button from "~/components/ui/Button.vue";

const auth = useAuthStore();
const router = useRouter();

async function handleLogout() {
  try {
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
    <div class="mx-auto flex max-w-6xl items-center justify-between px-3 sm:px-6 py-2.5 sm:py-3 gap-2">
      <div class="flex items-center gap-2 sm:gap-4 md:gap-8 min-w-0">
        <NuxtLink
          to="/"
          class="flex items-center gap-2 text-sm sm:text-base font-bold tracking-tight text-foreground hover:text-primary transition-colors group shrink-0"
        >
          <div class="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg bg-primary text-white shadow-2xs group-hover:bg-primary-hover transition-colors">
            <Icon name="lucide:store" class="size-3.5 sm:size-4" aria-hidden="true" />
          </div>
          <span class="hidden xs:inline">Marketplace Studio</span>
          <span class="xs:hidden">Studio</span>
        </NuxtLink>

        <nav class="flex items-center gap-0.5 sm:gap-1" role="navigation" aria-label="Main Navigation">
          <NuxtLink
            to="/"
            class="flex items-center gap-1 sm:gap-1.5 rounded-lg px-2 sm:px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
          >
            <Icon name="lucide:layout-dashboard" class="size-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">Dashboard</span>
          </NuxtLink>
          <NuxtLink
            to="/library"
            class="flex items-center gap-1 sm:gap-1.5 rounded-lg px-2 sm:px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
            data-testid="nav-library-link"
          >
            <Icon name="lucide:images" class="size-3.5" aria-hidden="true" />
            <span class="hidden md:inline">Mockup Library</span>
            <span class="hidden sm:inline md:hidden">Library</span>
          </NuxtLink>
          <NuxtLink
            to="/settings"
            class="flex items-center gap-1 sm:gap-1.5 rounded-lg px-2 sm:px-3 py-1.5 text-xs font-semibold text-secondary-foreground hover:bg-secondary hover:text-foreground transition-colors"
            active-class="bg-blue-50 text-primary font-bold border border-blue-200"
            data-testid="nav-settings-link"
          >
            <Icon name="lucide:settings" class="size-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">Settings</span>
          </NuxtLink>
        </nav>
      </div>

      <div v-if="auth.user" class="flex items-center gap-1.5 sm:gap-3 shrink-0">
        <div class="hidden md:flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-3 py-1 text-xs text-secondary-foreground shadow-2xs">
          <Icon name="lucide:user" class="size-3.5 text-muted-foreground" aria-hidden="true" />
          <span class="font-medium truncate max-w-[140px]" data-testid="user-email">
            {{ auth.user.email }}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          data-testid="logout-btn"
          class="h-8 gap-1.5 px-2 sm:px-2.5 text-xs font-medium text-secondary-foreground hover:bg-secondary hover:text-destructive transition-colors cursor-pointer"
          @click="handleLogout"
        >
          <Icon name="lucide:log-out" class="size-3.5" aria-hidden="true" />
          <span class="hidden xs:inline">Logout</span>
        </Button>
      </div>
    </div>
  </header>
</template>
