<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import type { ListingDraft } from '~/types/listing';
import { useEtsy } from '~/composables/useEtsy';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import Alert from '~/components/ui/Alert.vue';

const props = defineProps<{
  workflowId: string;
  workflowState: string;
  listing?: ListingDraft | null;
}>();

const emit = defineEmits<{
  (e: 'draft-created'): void;
}>();

const {
  connectionStatus,
  draftStatus,
  isLoading,
  isDispatching,
  isReconciling,
  errorMessage,
  fetchConnectionStatus,
  triggerCreateEtsyDraft,
  fetchDraftStatus,
} = useEtsy();

let pollInterval: ReturnType<typeof setInterval> | null = null;
let reconciliationInterval: ReturnType<typeof setInterval> | null = null;
let isReconcilingInProgress = false;
const copied = ref(false);

const currentStatus = computed(() => {
  return draftStatus.value?.dispatch_status || props.listing?.etsy_dispatch_status || 'not_started';
});

const isDraftRemoved = computed(() => {
  return currentStatus.value === 'draft_removed';
});

const isGate3Approved = computed(() => {
  return ['READY_FOR_ETSY_DRAFT', 'ETSY_DRAFT_CREATED', 'PUBLISHED'].includes(props.workflowState);
});

const isCompleted = computed(() => {
  if (isDraftRemoved.value) return false;
  return (
    currentStatus.value === 'completed' ||
    (props.workflowState === 'ETSY_DRAFT_CREATED' && Boolean(listingId.value))
  );
});

const isInProgress = computed(() => {
  return (
    ['queued', 'creating_listing', 'uploading_images', 'uploading_file'].includes(currentStatus.value) ||
    isDispatching.value
  );
});

const isFailed = computed(() => {
  return currentStatus.value === 'failed';
});

const failureReason = computed(() => {
  return (
    errorMessage.value ||
    draftStatus.value?.error_message ||
    props.listing?.etsy_failure_reason ||
    'The Etsy dispatch process encountered an issue. Please verify shop connection and retry.'
  );
});

const listingId = computed(() => {
  if (isDraftRemoved.value) return null;
  return draftStatus.value?.etsy_listing_id || props.listing?.etsy_listing_id || null;
});

const mockupCount = computed(() => {
  return props.listing?.etsy_image_ids?.length || draftStatus.value?.etsy_image_ids?.length || 0;
});

const digitalFilesCount = computed(() => {
  return props.listing?.etsy_file_ids?.length || draftStatus.value?.etsy_file_ids?.length || (props.listing?.etsy_file_id || draftStatus.value?.etsy_file_id ? 1 : 0);
});

const listingManagerUrl = computed(() => {
  if (!listingId.value) return null;
  return `https://www.etsy.com/your/shops/me/listing-editor/edit/${listingId.value}`;
});

const draftListingsUrl = computed(() => {
  return 'https://www.etsy.com/your/shops/me/tools/listings/state:draft';
});

onMounted(async () => {
  await fetchConnectionStatus();
  if (isInProgress.value) {
    startPolling();
  } else if (props.workflowState === 'ETSY_DRAFT_CREATED' || isCompleted.value || Boolean(listingId.value)) {
    // Reconcile on page load
    const updated = await fetchDraftStatus(props.workflowId);
    if (updated?.dispatch_status === 'draft_removed') {
      emit('draft-created');
    } else if (props.workflowState === 'ETSY_DRAFT_CREATED' || updated?.dispatch_status === 'completed') {
      startReconciliationPolling();
    }
  }
});

onBeforeUnmount(() => {
  stopPolling();
  stopReconciliationPolling();
});

watch(currentStatus, (newStatus) => {
  if (['queued', 'creating_listing', 'uploading_images', 'uploading_file'].includes(newStatus)) {
    startPolling();
  } else if (newStatus === 'completed') {
    stopPolling();
    startReconciliationPolling();
    emit('draft-created');
  } else if (newStatus === 'draft_removed') {
    stopPolling();
    stopReconciliationPolling();
    emit('draft-created');
  } else if (newStatus === 'failed') {
    stopPolling();
  }
});

function startPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(async () => {
    const updated = await fetchDraftStatus(props.workflowId);
    if (updated?.dispatch_status === 'completed') {
      stopPolling();
      startReconciliationPolling();
      emit('draft-created');
    } else if (updated?.dispatch_status === 'failed') {
      stopPolling();
    } else if (updated?.dispatch_status === 'draft_removed') {
      stopPolling();
      stopReconciliationPolling();
      emit('draft-created');
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function startReconciliationPolling() {
  if (reconciliationInterval) return;
  reconciliationInterval = setInterval(async () => {
    if (isReconcilingInProgress || isDispatching.value) return;
    if (props.workflowState !== 'ETSY_DRAFT_CREATED' && !isCompleted.value) {
      stopReconciliationPolling();
      return;
    }
    isReconcilingInProgress = true;
    try {
      const updated = await fetchDraftStatus(props.workflowId);
      if (updated?.dispatch_status === 'draft_removed') {
        stopReconciliationPolling();
        emit('draft-created');
      }
    } finally {
      isReconcilingInProgress = false;
    }
  }, 15000);
}

function stopReconciliationPolling() {
  if (reconciliationInterval) {
    clearInterval(reconciliationInterval);
    reconciliationInterval = null;
  }
}

async function handleCreateDraft() {
  const result = await triggerCreateEtsyDraft(props.workflowId);
  if (result) {
    startPolling();
  }
}

async function copyListingId() {
  if (!listingId.value) return;
  try {
    await navigator.clipboard.writeText(listingId.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Ignore clipboard error
  }
}
</script>

<template>
  <Card
    class="shadow-xs border border-border bg-card transition-all duration-200"
    data-testid="etsy-draft-card"
  >
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-start sm:items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-2xs"
          >
            <Icon name="lucide:store" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base font-semibold flex items-center gap-2">
              <span>Etsy Listing Dispatch</span>
              <span
                v-if="connectionStatus?.connected && (connectionStatus.shop_name || props.listing.etsy_shop_id)"
                class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-normal rounded-md bg-muted text-foreground border border-border"
              >
                <span class="size-1.5 rounded-full bg-emerald-500" />
                {{ connectionStatus.shop_name || 'Connected Shop' }}
              </span>
            </CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Uploads print-ready master artwork, mockups, and customer bundle as a private draft.
            </CardDescription>
          </div>
        </div>

        <Badge
          v-if="isReconciling"
          variant="outline"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 text-muted-foreground bg-muted/40 border-border animate-pulse"
          data-testid="etsy-badge-checking"
        >
          <Icon name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
          <span>Checking Etsy draft…</span>
        </Badge>
        <Badge
          v-else-if="isCompleted"
          variant="outline"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 text-foreground bg-muted/50 border-border"
          data-testid="etsy-badge-completed"
        >
          <Icon name="lucide:circle-check" class="size-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>Draft Created</span>
        </Badge>
        <Badge
          v-else-if="isDraftRemoved"
          variant="outline"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/20"
          data-testid="etsy-badge-removed"
        >
          <Icon name="lucide:info" class="size-3" aria-hidden="true" />
          <span>Etsy Draft Removed</span>
        </Badge>
        <Badge
          v-else-if="isInProgress"
          variant="warning"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 animate-pulse"
          data-testid="etsy-badge-progress"
        >
          <Icon name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
          <span>Dispatching...</span>
        </Badge>
        <Badge
          v-else-if="isFailed"
          variant="destructive"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0"
          data-testid="etsy-badge-failed"
        >
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Dispatch Failed</span>
        </Badge>
        <Badge
          v-else-if="!isGate3Approved"
          variant="outline"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 text-muted-foreground bg-muted/30 border-border"
          data-testid="etsy-badge-pending-gate"
        >
          <Icon name="lucide:clock-3" class="size-3 text-muted-foreground" aria-hidden="true" />
          <span>Awaiting Gate 3</span>
        </Badge>
        <Badge
          v-else
          variant="secondary"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0"
          data-testid="etsy-badge-ready"
        >
          <Icon name="lucide:clock-3" class="size-3 text-muted-foreground" aria-hidden="true" />
          <span>Ready for Dispatch</span>
        </Badge>
      </div>
    </CardHeader>

    <CardContent class="pt-4 space-y-4">
      <!-- Error / Failure Alert -->
      <Alert
        v-if="isFailed || errorMessage"
        variant="destructive"
        title="Etsy Dispatch Failed"
        :description="failureReason"
        action-label="Retry Dispatch"
        @action="handleCreateDraft"
      />

      <!-- Draft Removed Alert -->
      <Alert
        v-if="isDraftRemoved"
        variant="info"
        title="Etsy draft removed"
        description="This draft no longer exists in Etsy. Your campaign and digital files are still available locally."
        data-testid="etsy-draft-removed-alert"
      />

      <!-- Shop Not Connected Alert -->
      <Alert
        v-if="!connectionStatus?.connected && !isLoading"
        variant="warning"
        title="Etsy Shop Not Connected"
        description="Connect your Etsy shop in Settings before creating draft listings."
      >
        <template #action>
          <NuxtLink to="/settings">
            <Button variant="outline" size="sm" class="text-xs h-8 gap-1.5 cursor-pointer">
              <Icon name="lucide:settings" class="size-3.5" aria-hidden="true" />
              <span>Open Settings</span>
            </Button>
          </NuxtLink>
        </template>
      </Alert>

      <!-- In-Progress Steps Stepper -->
      <div
        v-if="isInProgress"
        class="bg-muted/40 border border-border rounded-xl p-4 space-y-3"
        data-testid="etsy-dispatching-progress"
      >
        <div class="flex items-center justify-between text-xs font-semibold text-foreground">
          <span>Dispatching Draft to Etsy Open API v3...</span>
          <span class="font-mono text-primary animate-pulse">In Progress</span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
          <!-- Step 1: Listing Creation -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              currentStatus === 'creating_listing'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : currentStatus !== 'queued'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                currentStatus === 'creating_listing'
                  ? 'lucide:loader-circle'
                  : currentStatus !== 'queued'
                    ? 'lucide:circle-check'
                    : 'lucide:circle'
              "
              :class="['size-4 shrink-0', currentStatus === 'creating_listing' ? 'animate-spin text-primary' : (currentStatus !== 'queued' ? 'text-emerald-600' : '')]"
              aria-hidden="true"
            />
            <span>1. Create Listing</span>
          </div>

          <!-- Step 2: Upload Mockups -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              currentStatus === 'uploading_images'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : ['uploading_file', 'completed'].includes(currentStatus)
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                currentStatus === 'uploading_images'
                  ? 'lucide:loader-circle'
                  : ['uploading_file', 'completed'].includes(currentStatus)
                    ? 'lucide:circle-check'
                    : 'lucide:circle'
              "
              :class="['size-4 shrink-0', currentStatus === 'uploading_images' ? 'animate-spin text-primary' : (['uploading_file', 'completed'].includes(currentStatus) ? 'text-emerald-600' : '')]"
              aria-hidden="true"
            />
            <span>2. Upload Mockups</span>
          </div>

          <!-- Step 3: Upload Digital Files -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              currentStatus === 'uploading_file'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : currentStatus === 'completed'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                currentStatus === 'uploading_file'
                  ? 'lucide:loader-circle'
                  : currentStatus === 'completed'
                    ? 'lucide:circle-check'
                    : 'lucide:circle'
              "
              :class="['size-4 shrink-0', currentStatus === 'uploading_file' ? 'animate-spin text-primary' : (currentStatus === 'completed' ? 'text-emerald-600' : '')]"
              aria-hidden="true"
            />
            <span>3. Upload Digital Files</span>
          </div>
        </div>
      </div>

      <!-- Completed Success Panel -->
      <div v-if="isCompleted" class="space-y-3" data-testid="etsy-completed-panel">
        <!-- Compact Refined Stats Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-muted/30 border border-border/80 p-3 rounded-lg text-xs">
          <!-- Listing ID -->
          <div class="flex flex-col justify-center px-1">
            <span class="text-[11px] text-muted-foreground">Listing ID</span>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="font-mono text-xs font-semibold text-foreground tracking-tight">
                {{ listingId || 'N/A' }}
              </span>
              <button
                v-if="listingId"
                type="button"
                class="text-muted-foreground hover:text-foreground cursor-pointer p-0.5 rounded hover:bg-secondary transition-colors"
                title="Copy Listing ID"
                @click="copyListingId"
              >
                <Icon :name="copied ? 'lucide:check' : 'lucide:copy'" class="size-3 text-muted-foreground hover:text-foreground" aria-hidden="true" />
              </button>
            </div>
          </div>

          <!-- Listing State -->
          <div class="flex flex-col justify-center px-1">
            <span class="text-[11px] text-muted-foreground">Listing State</span>
            <span class="inline-flex items-center gap-1 text-xs font-medium text-foreground mt-0.5">
              <Icon name="lucide:shield-check" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span>Draft (Safe)</span>
            </span>
          </div>

          <!-- Mockups Count -->
          <div class="flex flex-col justify-center px-1">
            <span class="text-[11px] text-muted-foreground">Mockups</span>
            <span class="text-xs font-medium text-foreground mt-0.5">
              {{ mockupCount }} Mockups
            </span>
          </div>

          <!-- Customer Delivery -->
          <div class="flex flex-col justify-center px-1">
            <span class="text-[11px] text-muted-foreground">Customer Files</span>
            <span class="text-xs font-medium text-foreground inline-flex items-center gap-1 mt-0.5 truncate">
              <Icon name="lucide:file-check" class="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
              <span class="truncate">{{ digitalFilesCount > 1 ? `${digitalFilesCount} Real Files` : 'Digital Product Attached' }}</span>
            </span>
          </div>
        </div>

        <!-- Action Toolbar -->
        <div class="flex items-center justify-end gap-2 pt-1">
          <a
            v-if="listingManagerUrl"
            :href="listingManagerUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button
              variant="default"
              size="sm"
              class="gap-2 cursor-pointer shadow-xs font-semibold"
              data-testid="etsy-open-manager-btn"
            >
              <Icon name="lucide:external-link" class="size-3.5" aria-hidden="true" />
              <span>Open in Etsy Shop Manager</span>
            </Button>
          </a>

          <a
            :href="draftListingsUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button
              variant="outline"
              size="sm"
              class="gap-1.5 cursor-pointer text-xs font-medium"
              title="Open all Etsy Draft Listings"
            >
              <Icon name="lucide:layers" class="size-3.5 text-muted-foreground" aria-hidden="true" />
              <span>All Drafts</span>
            </Button>
          </a>
        </div>
      </div>

      <!-- Ready to Dispatch Action -->
      <div
        v-else-if="!isInProgress"
        class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1"
        data-testid="etsy-ready-dispatch-section"
      >
        <div class="text-xs text-muted-foreground space-y-0.5">
          <div class="font-semibold text-foreground">
            {{ isDraftRemoved ? 'Create New Etsy Draft' : isGate3Approved ? 'Ready for Draft Creation' : 'Gate 3 Approval Required' }}
          </div>
          <div>
            {{ isDraftRemoved ? 'Generate a new official Etsy draft listing with the approved campaign files.' : isGate3Approved ? 'Creates an official draft listing on your connected Etsy shop with all approved assets.' : 'Approve Gate 3 below to authorize and create draft listing on Etsy.' }}
          </div>
        </div>

        <Button
          variant="default"
          size="sm"
          class="gap-2 cursor-pointer shrink-0 font-semibold"
          :disabled="!connectionStatus?.connected || isDispatching || !isGate3Approved"
          data-testid="etsy-create-draft-btn"
          @click="handleCreateDraft"
        >
          <Icon v-if="isDispatching" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:store" class="size-4" aria-hidden="true" />
          <span>{{ !isGate3Approved ? 'Awaiting Approval' : 'Create Etsy Draft' }}</span>
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
