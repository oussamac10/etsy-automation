<script setup lang="ts">
/* global useRouter */
import { useAuthStore } from "~/stores/auth";

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
  <nav class="border-b border-slate-200 bg-white shadow-sm" role="navigation" aria-label="Main Navigation">
    <div class="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-6">
        <NuxtLink to="/" class="text-lg font-bold text-slate-800 hover:text-sky-600 transition-colors">
          Etsy Automation
        </NuxtLink>
        <div class="flex gap-4">
          <NuxtLink
            to="/"
            class="text-sm font-medium text-slate-600 hover:text-sky-600 transition-colors"
            active-class="text-sky-600 border-b-2 border-sky-600 pb-1"
          >
            Dashboard
          </NuxtLink>
          <NuxtLink
            to="/settings"
            class="text-sm font-medium text-slate-600 hover:text-sky-600 transition-colors"
            active-class="text-sky-600 border-b-2 border-sky-600 pb-1"
            data-testid="nav-settings-link"
          >
            Settings
          </NuxtLink>
        </div>
      </div>
      <div v-if="auth.user" class="flex items-center gap-4">
        <span class="text-xs text-slate-500 hidden sm:inline" data-testid="user-email">
          {{ auth.user.email }}
        </span>
        <button
          type="button"
          class="inline-flex justify-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500"
          data-testid="logout-btn"
          @click="handleLogout"
        >
          Logout
        </button>
      </div>
    </div>
  </nav>
</template>
