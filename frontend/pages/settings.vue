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

interface CredentialItem {
  provider: string;
  configured: boolean;
  masked_value: string | null;
  label: string | null;
  updated_at: string | null;
}
const credentialsList = ref<CredentialItem[]>([]);
const credentialsError = ref<string | null>(null);
const isCredentialsLoading = ref(false);
const newSecrets = ref<Record<string, string>>({});
const keyLabels = ref<Record<string, string>>({});

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

async function fetchCredentials(): Promise<void> {
  credentialsError.value = null;
  isCredentialsLoading.value = true;
  try {
    const data = await $fetch<{ items: CredentialItem[] }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/settings/credentials`,
      { credentials: "include" }
    );
    credentialsList.value = (data?.items || []).filter((item) =>
      ["gemini", "tavily", "recraft", "openai", "etsy", "uspto"].includes(item.provider)
    );
  } catch {
    credentialsList.value = [];
  } finally {
    isCredentialsLoading.value = false;
  }
}

async function saveCredential(provider: string): Promise<void> {
  const secret = newSecrets.value[provider];
  if (!secret) return;
  credentialsError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }
    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/settings/credentials/${provider}`,
      {
        method: "PUT",
        headers,
        body: {
          secret,
          label: keyLabels.value[provider] || null,
        },
        credentials: "include",
      }
    );
    newSecrets.value[provider] = "";
    keyLabels.value[provider] = "";
    await fetchCredentials();
  } catch {
    credentialsError.value = `Failed to save credential for ${provider}.`;
  }
}

async function removeCredential(provider: string): Promise<void> {
  credentialsError.value = null;
  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }
    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/settings/credentials/${provider}`,
      {
        method: "DELETE",
        headers,
        credentials: "include",
      }
    );
    await fetchCredentials();
  } catch {
    credentialsError.value = `Failed to remove credential for ${provider}.`;
  }
}

onMounted(() => {
  fetchTelegramStatus();
  fetchCredentials();
});
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

      <!-- Credentials Management Section -->
      <section aria-labelledby="credentials-heading" class="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="credentials-heading" class="mb-3 text-xl font-medium text-slate-800">API Connection Keys</h2>
        <p class="mb-6 text-sm text-slate-600">
          Configure API connection credentials for market research (Tavily), structured generation (Gemini), and artwork candidate synthesis (Recraft).
        </p>

        <div v-if="isCredentialsLoading" class="text-slate-600 text-sm animate-pulse">
          Loading credentials status...
        </div>

        <div v-else-if="credentialsError" class="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
          <p>{{ credentialsError }}</p>
        </div>

        <div v-else class="space-y-6">
          <div v-for="cred in credentialsList" :key="cred.provider" class="border-b border-slate-100 pb-6 last:border-0 last:pb-0">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <!-- Key info -->
              <div class="space-y-1">
                <span class="text-xs font-bold uppercase tracking-wider text-indigo-600">{{ cred.provider }} API Key</span>
                <div class="flex items-center gap-2">
                  <span v-if="cred.configured" class="inline-flex items-center gap-1.5 text-xs text-green-700 font-medium">
                    <span class="inline-block h-2 w-2 rounded-full bg-green-600" />
                    Configured ({{ cred.masked_value }})
                  </span>
                  <span v-else class="inline-flex items-center gap-1.5 text-xs text-amber-700 font-medium">
                    <span class="inline-block h-2 w-2 rounded-full bg-amber-600" />
                    Not Configured
                  </span>
                </div>
                <p v-if="cred.updated_at" class="text-[11px] text-slate-400">
                  Last updated: {{ new Date(cred.updated_at).toLocaleString() }}
                </p>
              </div>

              <!-- Key actions -->
              <div class="flex items-center gap-2 max-w-md w-full sm:w-auto">
                <div v-if="!cred.configured" class="flex items-center gap-2 w-full">
                  <input
                    type="password"
                    v-model="newSecrets[cred.provider]"
                    placeholder="Enter API key"
                    class="rounded-lg border-slate-200 text-sm focus:ring-indigo-500 focus:border-indigo-500 w-full"
                  />
                  <button
                    type="button"
                    :disabled="!newSecrets[cred.provider]"
                    class="inline-flex justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
                    @click="saveCredential(cred.provider)"
                  >
                    Save
                  </button>
                </div>
                <div v-else class="flex items-center justify-end gap-2 w-full">
                  <button
                    type="button"
                    class="inline-flex justify-center rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 cursor-pointer"
                    @click="removeCredential(cred.provider)"
                  >
                    Delete Key
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
