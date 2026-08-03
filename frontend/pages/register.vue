<script setup lang="ts">
/* global useRouter */
import { useAuthStore } from "~/stores/auth";

const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const displayName = ref("");
const password = ref("");
const error = ref<string | null>(null);
const loading = ref(false);

async function handleRegister() {
  if (!email.value || !displayName.value || !password.value) {
    error.value = "All fields are required.";
    return;
  }
  if (password.value.length < 8) {
    error.value = "Password must be at least 8 characters long.";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await auth.register(email.value, displayName.value, password.value);
    router.push("/");
  } catch (err: unknown) {
    const errorData = err as { data?: { detail?: string } };
    if (errorData.data && errorData.data.detail) {
      error.value = errorData.data.detail;
    } else {
      error.value = "Registration failed. Please try again.";
    }
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
        <p class="mt-2 text-sm text-slate-500">Create a new owner account</p>
      </header>

      <form class="space-y-4" @submit.prevent="handleRegister">
        <div>
          <label for="displayName" class="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
            Display Name
          </label>
          <input
            id="displayName"
            v-model="displayName"
            type="text"
            required
            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="John Doe"
            data-testid="register-name-input"
          >
        </div>

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
            data-testid="register-email-input"
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
            autocomplete="new-password"
            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="••••••••"
            data-testid="register-password-input"
          >
        </div>

        <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800" role="alert" data-testid="register-error">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full inline-flex justify-center rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          data-testid="register-submit-btn"
        >
          {{ loading ? 'Creating Account...' : 'Sign Up' }}
        </button>
      </form>

      <footer class="mt-6 text-center text-xs text-slate-500">
        Already have an account?
        <NuxtLink to="/login" class="font-medium text-sky-600 hover:text-sky-800 transition-colors">
          Sign In
        </NuxtLink>
      </footer>
    </div>
  </main>
</template>
