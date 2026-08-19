<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useEtsy } from '~/composables/useEtsy';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import Alert from '~/components/ui/Alert.vue';
import AlertTitle from '~/components/ui/AlertTitle.vue';
import AlertDescription from '~/components/ui/AlertDescription.vue';
import Dialog from '~/components/ui/Dialog.vue';
import DialogHeader from '~/components/ui/DialogHeader.vue';
import DialogTitle from '~/components/ui/DialogTitle.vue';
import DialogDescription from '~/components/ui/DialogDescription.vue';
import DialogFooter from '~/components/ui/DialogFooter.vue';

let route: any = null;
let router: any = null;

try {
  route = useRoute();
} catch {
  route = { query: {} };
}

try {
  router = useRouter();
} catch {
  router = { replace: () => {} };
}

const {
  connectionStatus,
  isLoading,
  isConnecting,
  isDisconnecting,
  errorMessage,
  fetchConnectionStatus,
  initiateOAuthConnect,
  disconnectShop,
} = useEtsy();

const successFeedback = ref<string | null>(null);
const oauthError = ref<string | null>(null);
const showDisconnectModal = ref(false);

onMounted(async () => {
  if (route?.query?.etsy === 'connected') {
    successFeedback.value = 'Etsy shop connected successfully!';
    // Clean up query param
    router?.replace?.({ query: { ...route.query, etsy: undefined } });
  } else if (route?.query?.etsy === 'error') {
    oauthError.value = typeof route.query?.message === 'string' ? route.query.message : 'Etsy connection failed.';
    router?.replace?.({ query: { ...route.query, etsy: undefined, message: undefined } });
  }

  await fetchConnectionStatus();
});

function openDisconnectModal(): void {
  showDisconnectModal.value = true;
}

async function confirmDisconnect(): Promise<void> {
  const success = await disconnectShop();
  if (success) {
    successFeedback.value = null;
    oauthError.value = null;
    showDisconnectModal.value = false;
  }
}

async function handleConnect(): Promise<void> {
  successFeedback.value = null;
  oauthError.value = null;
  await initiateOAuthConnect();
}
</script>

<template>
  <Card class="shadow-2xs" data-testid="etsy-connection-card">
    <CardHeader class="pb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-primary border border-border">
            <Icon name="lucide:store" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-lg">Etsy Shop Connection</CardTitle>
            <CardDescription>
              Connect your official Etsy seller account via OAuth 2.0 PKCE to automatically create draft listings
            </CardDescription>
          </div>
        </div>

        <Badge
          v-if="connectionStatus?.connected && connectionStatus.token_health === 'valid'"
          variant="success"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-status-connected"
        >
          <Icon name="lucide:circle-check" class="size-3" aria-hidden="true" />
          <span>Connected</span>
        </Badge>
        <Badge
          v-else-if="connectionStatus?.connected && connectionStatus.token_health === 'reauthorization_required'"
          variant="destructive"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-status-reauth"
        >
          <Icon name="lucide:triangle-alert" class="size-3" aria-hidden="true" />
          <span>Reauthorization Required</span>
        </Badge>
        <Badge
          v-else
          variant="secondary"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-status-disconnected"
        >
          <Icon name="lucide:clock-3" class="size-3" aria-hidden="true" />
          <span>Disconnected</span>
        </Badge>
      </div>
    </CardHeader>

    <CardContent class="pt-2">
      <!-- Loading State -->
      <div v-if="isLoading" class="text-muted-foreground text-sm animate-pulse py-4 flex items-center gap-2">
        <Icon name="lucide:loader-circle" class="size-4 animate-spin text-primary" aria-hidden="true" />
        <span>Loading Etsy integration status...</span>
      </div>

      <!-- Feedback Alerts -->
      <div v-else class="space-y-4">
        <Alert v-if="successFeedback && connectionStatus?.connected" variant="success" class="flex items-center justify-between">
          <div>
            <Icon name="lucide:circle-check" class="size-4" aria-hidden="true" />
            <AlertTitle>Connection Successful</AlertTitle>
            <AlertDescription>{{ successFeedback }}</AlertDescription>
          </div>
          <button
            type="button"
            class="text-emerald-700 hover:text-emerald-900 p-1 cursor-pointer rounded-lg hover:bg-emerald-100/50"
            aria-label="Dismiss"
            @click="successFeedback = null"
          >
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </Alert>

        <Alert v-if="oauthError || errorMessage" variant="destructive">
          <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
          <AlertTitle>Etsy Connection Notice</AlertTitle>
          <AlertDescription class="flex items-center justify-between">
            <span>{{ oauthError || errorMessage }}</span>
            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" class="h-7 text-xs cursor-pointer" @click="fetchConnectionStatus">
                Retry
              </Button>
              <button
                type="button"
                class="text-red-700 hover:text-red-900 p-1 cursor-pointer rounded-lg hover:bg-red-100/50"
                aria-label="Dismiss"
                @click="() => { oauthError = null; errorMessage = null; }"
              >
                <Icon name="lucide:x" class="size-4" aria-hidden="true" />
              </button>
            </div>
          </AlertDescription>
        </Alert>

        <!-- Connected View -->
        <div v-if="connectionStatus?.connected" class="space-y-4" data-testid="etsy-connected-panel">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 bg-muted/40 p-4 rounded-xl border border-border text-sm">
            <div>
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">Shop Name</span>
              <span class="text-base font-bold text-foreground">{{ connectionStatus.shop_name || 'Active Shop' }}</span>
            </div>
            <div>
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">Shop ID</span>
              <span class="font-mono text-sm text-foreground">{{ connectionStatus.shop_id || 'N/A' }}</span>
            </div>
            <div>
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">OAuth Scopes</span>
              <div class="flex flex-wrap gap-1 mt-1">
                <Badge
                  v-for="scope in connectionStatus.granted_scopes"
                  :key="scope"
                  variant="outline"
                  class="text-2xs font-mono py-0 px-1.5"
                >
                  {{ scope }}
                </Badge>
              </div>
            </div>
            <div>
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">Token Security</span>
              <span class="text-xs text-muted-foreground flex items-center gap-1.5 mt-1">
                <Icon name="lucide:lock" class="size-3.5 text-primary" aria-hidden="true" />
                <span>AES-256 encrypted at rest &bull; Auto-refreshing</span>
              </span>
            </div>
          </div>

          <!-- Strict Safety Guarantee Notice -->
          <div class="flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground">
            <Icon name="lucide:shield-check" class="size-4 shrink-0 text-primary mt-0.5" aria-hidden="true" />
            <div>
              <strong class="text-foreground font-semibold">Strict Safety Guarantee:</strong>
              This application only creates <strong>draft listings</strong> with mockup previews and customer ZIP download bundles. It will never automatically activate, publish, or modify live active listings.
            </div>
          </div>

          <div class="flex items-center justify-between pt-2">
            <Button
              v-if="connectionStatus.token_health === 'reauthorization_required'"
              variant="default"
              size="sm"
              class="gap-1.5 cursor-pointer bg-amber-600 hover:bg-amber-700"
              :disabled="isConnecting"
              @click="handleConnect"
            >
              <Icon v-if="isConnecting" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
              <Icon v-else name="lucide:rotate-ccw" class="size-3.5" aria-hidden="true" />
              <span>Reconnect Shop</span>
            </Button>
            <div v-else></div>

            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30 gap-1.5 cursor-pointer"
              :disabled="isDisconnecting"
              data-testid="etsy-disconnect-button"
              @click="openDisconnectModal"
            >
              <Icon v-if="isDisconnecting" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
              <Icon v-else name="lucide:unplug" class="size-3.5" aria-hidden="true" />
              <span>Disconnect Shop</span>
            </Button>
          </div>
        </div>

        <!-- Disconnected View -->
        <div v-else class="space-y-4 py-2" data-testid="etsy-disconnected-panel">
          <p class="text-sm text-muted-foreground">
            Connect your shop using Etsy's standard OAuth 2.0 with PKCE authorization. You will be redirected to Etsy to authorize listing draft management. You will never need to enter API keys or passwords manually.
          </p>

          <div class="flex items-start gap-2.5 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            <Icon name="lucide:info" class="size-4 shrink-0 text-primary mt-0.5" aria-hidden="true" />
            <span>
              Requires an active Etsy seller account with at least one opened shop. Draft creations do not incur listing fees until you choose to publish them inside Etsy Shop Manager.
            </span>
          </div>

          <div class="pt-2">
            <Button
              variant="default"
              class="gap-2 cursor-pointer"
              :disabled="isConnecting"
              data-testid="etsy-connect-button"
              @click="handleConnect"
            >
              <Icon v-if="isConnecting" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
              <Icon v-else name="lucide:store" class="size-4" aria-hidden="true" />
              <span>{{ isConnecting ? 'Redirecting to Etsy...' : 'Connect Etsy Shop' }}</span>
            </Button>
          </div>
        </div>
      </div>
    </CardContent>

    <!-- Disconnect Confirmation Dialog Modal -->
    <Dialog :open="showDisconnectModal" max-width="md" @close="showDisconnectModal = false">
      <DialogHeader>
        <div class="flex items-center gap-3 text-destructive">
          <div class="h-10 w-10 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center justify-center shrink-0">
            <Icon name="lucide:unplug" class="size-5 text-destructive" aria-hidden="true" />
          </div>
          <div>
            <DialogTitle>Disconnect Etsy Shop</DialogTitle>
            <DialogDescription class="mt-1">
              Are you sure you want to disconnect <strong>{{ connectionStatus?.shop_name || 'your Etsy shop' }}</strong>?
            </DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <div class="py-2 text-xs text-muted-foreground space-y-2">
        <p>
          Disconnecting will remove all stored OAuth tokens from the secure server database. You can reconnect your shop at any time.
        </p>
      </div>

      <DialogFooter class="gap-2 sm:gap-0">
        <Button variant="outline" size="sm" :disabled="isDisconnecting" @click="showDisconnectModal = false">
          Cancel
        </Button>
        <Button
          variant="destructive"
          size="sm"
          class="gap-1.5 cursor-pointer"
          :disabled="isDisconnecting"
          data-testid="confirm-disconnect-button"
          @click="confirmDisconnect"
        >
          <Icon v-if="isDisconnecting" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:unplug" class="size-3.5" aria-hidden="true" />
          <span>{{ isDisconnecting ? 'Disconnecting...' : 'Disconnect Shop' }}</span>
        </Button>
      </DialogFooter>
    </Dialog>
  </Card>
</template>
