<script setup lang="ts">
/* global useRouter */
import { useAuthStore } from "~/stores/auth";
import { LayoutDashboard, Settings, LogOut, User, Sparkles } from "lucide-vue-next";
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
    class="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/85 backdrop-blur-md transition-all shadow-xs"
    role="banner"
  >
    <div class="mx-auto flex max-w-6xl items-center justify-between px-4 sm:px-6 py-3">
      <div class="flex items-center gap-8">
        <NuxtLink
          to="/"
          class="flex items-center gap-2.5 text-base font-bold tracking-tight text-slate-900 hover:text-sky-600 transition-colors group"
        >
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-white shadow-xs group-hover:bg-sky-700 transition-colors">
            <Sparkles class="h-4 w-4" />
          </div>
          <span>Etsy Automation</span>
        </NuxtLink>

        <nav class="flex items-center gap-1" role="navigation" aria-label="Main Navigation">
          <NuxtLink
            to="/"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
            active-class="bg-sky-50 text-sky-700 font-semibold"
          >
            <LayoutDashboard class="h-3.5 w-3.5" />
            <span>Dashboard</span>
          </NuxtLink>
          <NuxtLink
            to="/settings"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
            active-class="bg-sky-50 text-sky-700 font-semibold"
            data-testid="nav-settings-link"
          >
            <Settings class="h-3.5 w-3.5" />
            <span>Settings</span>
          </NuxtLink>
        </nav>
      </div>

      <div v-if="auth.user" class="flex items-center gap-3">
        <div class="flex items-center gap-2 rounded-full border border-slate-200/80 bg-slate-50/80 px-3 py-1 text-xs text-slate-600 shadow-2xs">
          <User class="h-3.5 w-3.5 text-slate-400" />
          <span class="hidden sm:inline font-medium" data-testid="user-email">
            {{ auth.user.email }}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          data-testid="logout-btn"
          class="h-8 gap-1.5 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-red-600 transition-colors"
          @click="handleLogout"
        >
          <LogOut class="h-3.5 w-3.5" />
          <span class="hidden xs:inline">Logout</span>
        </Button>
      </div>
    </div>
  </header>
</template>
