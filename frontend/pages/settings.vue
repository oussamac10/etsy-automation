<script setup lang="ts">
/* global $fetch */
import { ref, onMounted, onBeforeUnmount } from "vue";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

// Telegram integration states
interface TelegramStatus {
  paired: boolean;
  telegram_username: string | null;
  pairing_code_expires_at: string | null;
}

const telegramStatus = ref<TelegramStatus | null>(null);
const telegramError = ref<string | null>(null);
const isTelegramLoading = ref(false);
const activePairingCode = ref<string | null>(null);
const pairingCodeExpiresAt = ref<string | null>(null);
const countdownText = ref("");
let countdownInterval: ReturnType<typeof setInterval> | null = null;

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

async function fetchTelegramStatus(): Promise<void> {
  telegramError.value = null;
  try {
    const data = await $fetch<TelegramStatus>(`${apiBase.replace(/\/$/, "")}/api/v1/settings/telegram`, {
      credentials: "include"
    });
    telegramStatus.value = data;
    if (data && !data.paired && data.pairing_code_expires_at) {
      pairingCodeExpiresAt.value = data.pairing_code_expires_at;
      startCountdown();
    } else {
      pairingCodeExpiresAt.value = null;
      activePairingCode.value = null;
      stopCountdown();
    }
  } catch {
    telegramError.value = "Failed to load Telegram settings.";
  }
}

async function generateCode(): Promise<void> {
  isTelegramLoading.value = true;
  telegramError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    const data = await $fetch<{ pairing_code: string; expires_at: string }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/settings/telegram/pairing-code`,
      {
        method: "POST",
        headers,
        credentials: "include"
      }
    );
    activePairingCode.value = data.pairing_code;
    pairingCodeExpiresAt.value = data.expires_at;
    telegramStatus.value = { paired: false, telegram_username: null, pairing_code_expires_at: data.expires_at };
    startCountdown();
  } catch {
    telegramError.value = "Failed to generate pairing code.";
  } finally {
    isTelegramLoading.value = false;
  }
}

async function disconnectTelegram(): Promise<void> {
  isTelegramLoading.value = true;
  telegramError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    await $fetch(`${apiBase.replace(/\/$/, "")}/api/v1/settings/telegram`, {
      method: "DELETE",
      headers,
      credentials: "include"
    });
    activePairingCode.value = null;
    pairingCodeExpiresAt.value = null;
    telegramStatus.value = { paired: false, telegram_username: null, pairing_code_expires_at: null };
    stopCountdown();
  } catch {
    telegramError.value = "Failed to disconnect Telegram.";
  } finally {
    isTelegramLoading.value = false;
  }
}

function startCountdown(): void {
  stopCountdown();
  updateCountdown();
  countdownInterval = setInterval(updateCountdown, 1000);
}

function stopCountdown(): void {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
  countdownText.value = "";
}

function updateCountdown(): void {
  if (!pairingCodeExpiresAt.value) {
    stopCountdown();
    return;
  }
  const expiry = new Date(pairingCodeExpiresAt.value).getTime();
  const now = new Date().getTime();
  const diff = expiry - now;
  if (diff <= 0) {
    stopCountdown();
    activePairingCode.value = null;
    pairingCodeExpiresAt.value = null;
    countdownText.value = "Code expired. Please generate a new one.";
    return;
  }
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  countdownText.value = `Expires in ${minutes}m ${seconds}s`;
}

onMounted(fetchTelegramStatus);
onBeforeUnmount(stopCountdown);
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <NavBar />

    <main id="main" class="mx-auto max-w-4xl px-6 py-12">
      <header class="mb-10">
        <h1 class="text-3xl font-semibold tracking-tight text-slate-800">Owner Settings</h1>
        <p class="mt-2 max-w-2xl text-slate-600">
          Manage your account connection credentials, alert preferences, and active remote integrations.
        </p>
      </header>

      <section aria-labelledby="telegram-heading" class="mb-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="telegram-heading" class="mb-3 text-xl font-medium text-slate-800">Telegram Bot Remote Control</h2>
        <p class="mb-4 text-sm text-slate-600">
          Pair your Telegram account with this service to receive notifications, check statuses, list/cancel active jobs, and pause/resume automation runs directly from Telegram.
        </p>

        <div v-if="isTelegramLoading" class="text-slate-600 text-sm animate-pulse" data-testid="telegram-loading">
          Updating Telegram settings...
        </div>

        <div v-else-if="telegramError" class="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert" data-testid="telegram-error">
          <p>{{ telegramError }}</p>
          <button type="button" class="mt-2 font-medium text-red-600 hover:text-red-800 underline focus:ring-2 focus:ring-sky-500" @click="fetchTelegramStatus">
            Retry
          </button>
        </div>

        <div v-else>
          <!-- Case 1: Paired -->
          <div v-if="telegramStatus?.paired" class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" data-testid="telegram-paired-container">
            <div>
              <div class="flex items-center gap-2 text-green-700 font-medium">
                <span class="inline-block h-2.5 w-2.5 rounded-full bg-green-600" aria-hidden="true" />
                Connected to Telegram
              </div>
              <p v-if="telegramStatus.telegram_username" class="mt-1 text-sm text-slate-500" data-testid="telegram-username">
                Username: @{{ telegramStatus.telegram_username }}
              </p>
            </div>
            <button
              type="button"
              class="inline-flex justify-center rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
              data-testid="disconnect-btn"
              @click="disconnectTelegram"
            >
              Disconnect Bot
            </button>
          </div>

          <!-- Case 2: Unpaired -->
          <div v-else class="space-y-4" data-testid="telegram-unpaired-container">
            <div class="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              <h3 class="font-medium text-slate-800 mb-1">Setup Instructions:</h3>
              <ol class="list-decimal pl-5 space-y-1">
                <li>Open Telegram and search for the bot (e.g. <code>@EtsyAutomationBot</code>).</li>
                <li>Click <b>Start</b> or send <code>/start</code>.</li>
                <li>Generate a pairing code below and send it to the bot.</li>
              </ol>
            </div>

            <div v-if="activePairingCode" class="flex flex-col items-center justify-center p-4 border border-dashed border-slate-300 rounded-lg">
              <span class="text-xs text-slate-400 uppercase tracking-widest font-medium mb-1">Pairing Code</span>
              <div class="text-3xl font-mono font-bold tracking-wider text-slate-800 select-all mb-2" data-testid="pairing-code">
                {{ activePairingCode.slice(0,3) }} {{ activePairingCode.slice(3) }}
              </div>
              <span class="text-sm font-medium text-slate-500" data-testid="pairing-code-countdown">{{ countdownText }}</span>
            </div>

            <div class="flex gap-3">
              <button
                type="button"
                class="inline-flex justify-center rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
                data-testid="generate-pairing-code-btn"
                @click="generateCode"
              >
                {{ activePairingCode ? 'Regenerate Code' : 'Generate Pairing Code' }}
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
