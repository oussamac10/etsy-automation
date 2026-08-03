<script setup lang="ts">
/* global useRouter */
import { useAuthStore } from "~/stores/auth";

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const error = ref<string | null>(null);
const loading = ref(false);

async function handleLogin() {
  if (!email.value || !password.value) {
    error.value = "Please enter both email and password.";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch {
    error.value = "Invalid email or password.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main id="main" class="min-h-screen bg-slate-50 flex items-center justify-center p-6">
    <div class="w-full max-w-md bg-white rounded-2xl border border-slate-200 p-8 shadow-lg">
      <header class="mb-6 text-center">
        <h1 class="text-2xl font-bold tracking-tight text-slate-800">Etsy Automation</h1>
        <p class="mt-2 text-sm text-slate-500">Sign in to your owner dashboard</p>
      </header>

      <form class="space-y-4" @submit.prevent="handleLogin">
        <div>
          <label for="email" class="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
            Email Address
          </label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            autocomplete="email"
            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="owner@example.com"
            data-testid="login-email-input"
          >
        </div>

        <div>
          <label for="password" class="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
            Password
          </label>
          <input
            id="password"
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="••••••••"
            data-testid="login-password-input"
          >
        </div>

        <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800" role="alert" data-testid="login-error">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full inline-flex justify-center rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          data-testid="login-submit-btn"
        >
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
    </div>
  </main>
</template>
