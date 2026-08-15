<script setup lang="ts">
/* global $fetch */
import { ref, onMounted, onBeforeUnmount } from "vue";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";

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
      credentials: "include",
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
        credentials: "include",
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
      credentials: "include",
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
}

function updateCountdown(): void {
  if (!pairingCodeExpiresAt.value) {
    countdownText.value = "";
    stopCountdown();
    return;
  }
  const expiry = new Date(pairingCodeExpiresAt.value).getTime();
  const now = new Date().getTime();
  const diffSec = Math.max(0, Math.floor((expiry - now) / 1000));

  if (diffSec <= 0) {
    countdownText.value = "Code expired";
    activePairingCode.value = null;
    stopCountdown();
    return;
  }

  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  countdownText.value = `Expires in ${mins}m ${secs}s`;
}

async function fetchCredentials(): Promise<void> {
  isCredentialsLoading.value = true;
  credentialsError.value = null;
  try {
    const data = await $fetch<{ items: CredentialItem[] }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/settings/credentials`,
      { credentials: "include" }
    );
    credentialsList.value = data.items;
  } catch {
    credentialsError.value = "Failed to load credentials.";
  } finally {
    isCredentialsLoading.value = false;
  }
}

async function saveCredential(provider: string): Promise<void> {
  const secret = newSecrets.value[provider]?.trim();
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
  <div class="min-h-screen bg-zinc-50/80 pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-5xl px-4 sm:px-6 py-10 space-y-8">
      <!-- Page Header -->
      <header class="flex flex-col gap-1 border-b border-zinc-200/80 pb-6">
        <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-600">
          <Icon name="lucide:shield-check" class="size-4" aria-hidden="true" />
          <span>Security & Integrations</span>
        </div>
        <h1 class="text-3xl font-bold tracking-tight text-zinc-900">Owner Settings</h1>
        <p class="text-sm text-zinc-500 max-w-2xl">
          Manage API connection credentials, encryption keys, and active Telegram remote control pairings.
        </p>
      </header>

      <!-- Telegram Section -->
      <Card class="shadow-2xs">
        <CardHeader class="pb-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
                <Icon name="lucide:bot" class="size-5" aria-hidden="true" />
              </div>
              <div>
                <CardTitle class="text-lg">Telegram Bot Remote Control</CardTitle>
                <CardDescription>
                  Receive real-time progress notifications and control active runs via Telegram
                </CardDescription>
              </div>
            </div>
            <Badge v-if="telegramStatus?.paired" variant="success" class="gap-1 px-3 py-1 inline-flex items-center">
              <Icon name="lucide:circle-check" class="size-3" aria-hidden="true" />
              <span>Paired</span>
            </Badge>
            <Badge v-else variant="secondary" class="gap-1 px-3 py-1 text-zinc-600 inline-flex items-center">
              <Icon name="lucide:clock-3" class="size-3" aria-hidden="true" />
              <span>Unpaired</span>
            </Badge>
          </div>
        </CardHeader>

        <CardContent class="pt-2">
          <div v-if="isTelegramLoading" class="text-zinc-500 text-sm animate-pulse py-4 flex items-center gap-2" data-testid="telegram-loading">
            <Icon name="lucide:loader-circle" class="size-4 animate-spin text-indigo-600" aria-hidden="true" />
            <span>Updating Telegram settings...</span>
          </div>

          <Alert v-else-if="telegramError" variant="destructive" class="mb-4" data-testid="telegram-error">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertTitle>Connection Error</AlertTitle>
            <AlertDescription class="flex items-center justify-between">
              <span>{{ telegramError }}</span>
              <Button variant="outline" size="sm" class="h-7 text-xs cursor-pointer" @click="fetchTelegramStatus">
                Retry
              </Button>
            </AlertDescription>
          </Alert>

          <div v-else>
            <!-- Case 1: Paired -->
            <div
              v-if="telegramStatus?.paired"
              class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50/50 p-4"
              data-testid="telegram-paired-container"
            >
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                  <Icon name="lucide:circle-check" class="size-5" aria-hidden="true" />
                </div>
                <div>
                  <div class="flex items-center gap-2 text-emerald-900 font-semibold text-sm">
                    Connected to Telegram
                  </div>
                  <p v-if="telegramStatus.telegram_username" class="text-xs text-emerald-700 font-medium" data-testid="telegram-username">
                    Username: @{{ telegramStatus.telegram_username }}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                data-testid="disconnect-btn"
                class="gap-1.5 border-emerald-200 bg-white text-emerald-800 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 transition-colors shadow-2xs font-medium cursor-pointer inline-flex items-center"
                @click="disconnectTelegram"
              >
                <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
                <span>Disconnect Bot</span>
              </Button>
            </div>

            <!-- Case 2: Unpaired -->
            <div v-else class="space-y-4" data-testid="telegram-unpaired-container">
              <div class="rounded-xl bg-zinc-50 border border-zinc-200/80 p-4 text-xs text-zinc-600 space-y-2">
                <div class="flex items-center gap-1.5 font-semibold text-zinc-800 text-sm">
                  <Icon name="lucide:help-circle" class="size-4 text-indigo-600" aria-hidden="true" />
                  <span>Setup Instructions:</span>
                </div>
                <ol class="list-decimal pl-5 space-y-1 text-zinc-600 leading-relaxed">
                  <li>Open Telegram and search for the bot (e.g. <code class="bg-white px-1.5 py-0.5 rounded border border-zinc-200 text-indigo-700 font-mono font-semibold">@EtsyAutomationBot</code>).</li>
                  <li>Click <b>Start</b> or send <code class="bg-white px-1.5 py-0.5 rounded border border-zinc-200 font-mono">/start</code>.</li>
                  <li>Generate a pairing code below and send it to the bot within 10 minutes.</li>
                </ol>
              </div>

              <!-- Active Code display -->
              <div
                v-if="activePairingCode"
                class="flex flex-col items-center justify-center p-6 border-2 border-dashed border-indigo-200 bg-indigo-50/40 rounded-xl"
              >
                <span class="text-xs text-indigo-600 uppercase tracking-widest font-bold mb-1">Active Pairing Code</span>
                <div
                  class="text-4xl font-mono font-extrabold tracking-widest text-zinc-900 select-all my-2 px-4 py-1.5 bg-white rounded-lg border border-indigo-200 shadow-2xs"
                  data-testid="pairing-code"
                >
                  {{ activePairingCode.slice(0, 3) }} {{ activePairingCode.slice(3) }}
                </div>
                <div class="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 mt-1" data-testid="pairing-code-countdown">
                  <Icon name="lucide:clock-3" class="size-3.5 text-amber-600" aria-hidden="true" />
                  <span class="text-amber-700 font-mono">{{ countdownText }}</span>
                </div>
              </div>

              <div>
                <Button
                  variant="default"
                  size="default"
                  data-testid="generate-pairing-code-btn"
                  class="gap-2 shadow-2xs font-semibold cursor-pointer inline-flex items-center"
                  @click="generateCode"
                >
                  <Icon name="lucide:sparkles" class="size-4" aria-hidden="true" />
                  <span>{{ activePairingCode ? 'Regenerate Code' : 'Generate Pairing Code' }}</span>
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Credentials Management Section -->
      <Card class="shadow-2xs">
        <CardHeader class="pb-4">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
              <Icon name="lucide:key-round" class="size-5" aria-hidden="true" />
            </div>
            <div>
              <CardTitle class="text-lg">API Connection Keys</CardTitle>
              <CardDescription>
                Configure AES-GCM encrypted keys for Tavily, Gemini, and Recraft
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent class="pt-2">
          <div v-if="isCredentialsLoading" class="text-zinc-500 text-sm animate-pulse py-4 flex items-center gap-2">
            <Icon name="lucide:loader-circle" class="size-4 animate-spin text-indigo-600" aria-hidden="true" />
            <span>Loading credentials status...</span>
          </div>

          <Alert v-else-if="credentialsError" variant="destructive" class="mb-4">
            <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
            <AlertDescription>{{ credentialsError }}</AlertDescription>
          </Alert>

          <div v-else class="divide-y divide-zinc-100">
            <div
              v-for="cred in credentialsList"
              :key="cred.provider"
              class="py-4 first:pt-0 last:pb-0"
            >
              <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <!-- Provider info -->
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-bold capitalize text-zinc-900">{{ cred.provider }}</span>
                    <Badge v-if="cred.configured" variant="success" class="text-[11px] px-2 py-0">
                      Configured ({{ cred.masked_value }})
                    </Badge>
                    <Badge v-else variant="warning" class="text-[11px] px-2 py-0">
                      Not Configured
                    </Badge>
                  </div>
                  <p v-if="cred.updated_at" class="text-xs text-zinc-400">
                    Last updated: {{ new Date(cred.updated_at).toLocaleString() }}
                  </p>
                </div>

                <!-- Provider actions -->
                <div class="flex items-center gap-2 max-w-md w-full sm:w-auto">
                  <div v-if="!cred.configured" class="flex items-center gap-2 w-full">
                    <Input
                      v-model="newSecrets[cred.provider]"
                      type="password"
                      placeholder="Enter API key"
                      class="h-9 w-full sm:w-64"
                    />
                    <Button
                      variant="default"
                      size="sm"
                      :disabled="!newSecrets[cred.provider]"
                      class="h-9 gap-1 font-semibold shadow-2xs cursor-pointer inline-flex items-center"
                      @click="saveCredential(cred.provider)"
                    >
                      <Icon name="lucide:save" class="size-3.5" aria-hidden="true" />
                      <span>Save</span>
                    </Button>
                  </div>
                  <div v-else class="flex items-center justify-end gap-2 w-full">
                    <Button
                      variant="outline"
                      size="sm"
                      class="h-8 gap-1.5 text-xs text-zinc-600 border-zinc-200 bg-white hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 transition-colors shadow-2xs font-medium cursor-pointer inline-flex items-center"
                      @click="removeCredential(cred.provider)"
                    >
                      <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
                      <span>Delete Key</span>
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </main>
  </div>
</template>
