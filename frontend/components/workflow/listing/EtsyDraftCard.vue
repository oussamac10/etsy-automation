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
import EtsyDraftVerificationCard from '~/components/workflow/listing/EtsyDraftVerificationCard.vue';
import WorkflowStaleNotice from '~/components/workflow/WorkflowStaleNotice.vue';
import { useWorkflowContext } from '~/composables/useWorkflowContext';
import type { EtsyDraftVerification } from '~/types/etsy';

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

const {
  fetchContext,
  staleReasons,
  etsySyncStatus,
} = useWorkflowContext();

const etsyStaleReasons = computed(() => {
  if (etsySyncStatus.value === 'STALE') {
    return staleReasons.value;
  }
  return [];
});

onMounted(() => {
  if (props.workflowId) {
    fetchContext(props.workflowId);
  }
});

watch(
  () => props.workflowId,
  (newId) => {
    if (newId) fetchContext(newId);
  }
);

const currentStatus = computed(() => {
  return draftStatus.value?.dispatch_status || props.listing?.etsy_dispatch_status || 'not_started';
});

const isDraftRemoved = computed(() => {
  return currentStatus.value === 'draft_removed';
});

const isGate3Approved = computed(() => {
  return ['READY_FOR_ETSY_DRAFT', 'ETSY_DRAFT_CREATED', 'PUBLISHED'].includes(props.workflowState);
});

const isFailed = computed(() => {
  return currentStatus.value === 'failed';
});

const listingId = computed(() => {
  if (isDraftRemoved.value) return null;
  return draftStatus.value?.etsy_listing_id || props.listing?.etsy_listing_id || null;
});

const isCompleted = computed(() => {
  if (isDraftRemoved.value) return false;
  return (
    currentStatus.value === 'completed' ||
    (props.workflowState === 'ETSY_DRAFT_CREATED' &&
      Boolean(listingId.value) &&
      !['queued', 'creating_listing', 'uploading_images', 'uploading_file', 'uploading_files', 'applying_attributes'].includes(currentStatus.value))
  );
});

const isInProgress = computed(() => {
  if (isDraftRemoved.value || isCompleted.value || isFailed.value) return false;
  return (
    ['queued', 'creating_listing', 'uploading_images', 'uploading_file', 'uploading_files', 'applying_attributes'].includes(
      currentStatus.value
    ) || isDispatching.value
  );
});

const failureReason = computed(() => {
  return (
    errorMessage.value ||
    draftStatus.value?.error_message ||
    props.listing?.etsy_failure_reason ||
    'The Etsy dispatch process encountered an issue. Please verify shop connection and retry.'
  );
});

const mockupCount = computed(() => {
  return props.listing?.etsy_image_ids?.length || draftStatus.value?.etsy_image_ids?.length || 0;
});

const digitalFilesCount = computed(() => {
  return (
    props.listing?.etsy_file_ids?.length ||
    draftStatus.value?.etsy_file_ids?.length ||
    (props.listing?.etsy_file_id || draftStatus.value?.etsy_file_id ? 1 : 0)
  );
});

const listingManagerUrl = computed(() => {
  if (!listingId.value) return null;
  return `https://www.etsy.com/your/shops/me/listing-editor/edit/${listingId.value}`;
});

const draftListingsUrl = computed(() => {
  return 'https://www.etsy.com/your/shops/me/tools/listings/state:draft';
});

const stepStates = computed(() => {
  const status = currentStatus.value;
  const stepsData = draftStatus.value?.steps;

  const getStep = (key: 'create_listing' | 'upload_mockups' | 'upload_files' | 'apply_attributes') => {
    if (stepsData && stepsData[key]) {
      return stepsData[key].status;
    }
    if (isCompleted.value) return 'completed';
    if (isDraftRemoved.value) return 'pending';

    if (key === 'create_listing') {
      if (listingId.value) return 'completed';
      if (status === 'creating_listing' || status === 'queued') return 'in_progress';
      if (status === 'failed') return 'failed';
      return 'pending';
    }
    if (key === 'upload_mockups') {
      if (['uploading_file', 'uploading_files', 'applying_attributes', 'completed'].includes(status)) return 'completed';
      if (status === 'uploading_images') return 'in_progress';
      if (status === 'failed' && listingId.value && mockupCount.value === 0) return 'failed';
      if (mockupCount.value > 0 && isCompleted.value) return 'completed';
      return 'pending';
    }
    if (key === 'upload_files') {
      if (['applying_attributes', 'completed'].includes(status)) return 'completed';
      if (status === 'uploading_file' || status === 'uploading_files') return 'in_progress';
      if (status === 'failed' && mockupCount.value > 0 && digitalFilesCount.value === 0) return 'failed';
      if (digitalFilesCount.value > 0 && isCompleted.value) return 'completed';
      return 'pending';
    }
    if (key === 'apply_attributes') {
      if (status === 'completed') return 'completed';
      if (status === 'applying_attributes') return 'in_progress';
      if (status === 'failed' && digitalFilesCount.value > 0) return 'failed';
      return 'pending';
    }
    return 'pending';
  };

  return {
    create_listing: getStep('create_listing'),
    upload_mockups: getStep('upload_mockups'),
    upload_files: getStep('upload_files'),
    apply_attributes: getStep('apply_attributes'),
  };
});

const currentVerification = computed<EtsyDraftVerification | null>(() => {
  return draftStatus.value?.verification || props.listing?.etsy_verification_result || null;
});

function handleVerificationCompleted(report: EtsyDraftVerification) {
  if (draftStatus.value) {
    draftStatus.value.verification = report;
  }
}

onMounted(async () => {
  await fetchConnectionStatus();
  if (isInProgress.value) {
    const updated = await fetchDraftStatus(props.workflowId);
    if (updated?.dispatch_status === 'completed') {
      emit('draft-created');
      startReconciliationPolling();
    } else if (updated?.dispatch_status === 'draft_removed') {
      emit('draft-created');
    } else {
      startPolling();
    }
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
  if (['queued', 'creating_listing', 'uploading_images', 'uploading_file', 'uploading_files', 'applying_attributes'].includes(newStatus)) {
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
                v-if="connectionStatus?.connected && (connectionStatus.shop_name || props.listing?.etsy_shop_id)"
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
          <span>Creating Draft</span>
        </Badge>
        <Badge
          v-else-if="isFailed"
          variant="destructive"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0"
          data-testid="etsy-badge-failed"
        >
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Draft Failed</span>
        </Badge>
        <Badge
          v-else-if="!isGate3Approved"
          variant="outline"
          class="gap-1 px-2.5 py-0.5 text-xs font-medium shrink-0 text-muted-foreground bg-muted/30 border-border"
          data-testid="etsy-badge-pending-gate"
        >
          <Icon name="lucide:clock-3" class="size-3 text-muted-foreground" aria-hidden="true" />
          <span>Awaiting Approval</span>
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
      <!-- Out of Sync Notice -->
      <WorkflowStaleNotice
        v-if="isCompleted && etsyStaleReasons.length > 0"
        title="Etsy Draft Out of Sync"
        :reasons="etsyStaleReasons"
        action-label="Sync Changes to Etsy"
        :is-action-loading="isDispatching"
        @action="handleCreateDraft"
      />

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

      <!-- Steps Stepper (Visible during progress and after completion) -->
      <div
        v-if="isInProgress || isCompleted || (isFailed && listingId)"
        class="bg-muted/40 border border-border rounded-xl p-4 space-y-3"
        data-testid="etsy-dispatching-progress"
      >
        <div class="flex items-center justify-between text-xs font-semibold text-foreground">
          <span v-if="isCompleted">Etsy draft created successfully.</span>
          <span v-else-if="isInProgress">Dispatching Draft to Etsy Open API v3...</span>
          <span v-else>Etsy draft dispatch stopped.</span>

          <span v-if="isCompleted" class="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold font-mono">
            <Icon name="lucide:circle-check" class="size-3.5" aria-hidden="true" />
            <span>Complete</span>
          </span>
          <span v-else-if="isInProgress" class="font-mono text-primary animate-pulse">In Progress</span>
          <span v-else class="font-mono text-destructive">Failed</span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
          <!-- Step 1: Listing Creation -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              stepStates.create_listing === 'in_progress'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : stepStates.create_listing === 'completed'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : stepStates.create_listing === 'failed'
                    ? 'bg-destructive/10 border-destructive/30 text-destructive font-semibold'
                    : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                stepStates.create_listing === 'in_progress'
                  ? 'lucide:loader-circle'
                  : stepStates.create_listing === 'completed'
                    ? 'lucide:circle-check'
                    : stepStates.create_listing === 'failed'
                      ? 'lucide:circle-alert'
                      : 'lucide:circle'
              "
              :class="[
                'size-4 shrink-0',
                stepStates.create_listing === 'in_progress'
                  ? 'animate-spin text-primary'
                  : stepStates.create_listing === 'completed'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : stepStates.create_listing === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground/40',
              ]"
              aria-hidden="true"
            />
            <span class="truncate">1. Create Listing</span>
          </div>

          <!-- Step 2: Upload Mockups -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              stepStates.upload_mockups === 'in_progress'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : stepStates.upload_mockups === 'completed'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : stepStates.upload_mockups === 'failed'
                    ? 'bg-destructive/10 border-destructive/30 text-destructive font-semibold'
                    : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                stepStates.upload_mockups === 'in_progress'
                  ? 'lucide:loader-circle'
                  : stepStates.upload_mockups === 'completed'
                    ? 'lucide:circle-check'
                    : stepStates.upload_mockups === 'failed'
                      ? 'lucide:circle-alert'
                      : 'lucide:circle'
              "
              :class="[
                'size-4 shrink-0',
                stepStates.upload_mockups === 'in_progress'
                  ? 'animate-spin text-primary'
                  : stepStates.upload_mockups === 'completed'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : stepStates.upload_mockups === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground/40',
              ]"
              aria-hidden="true"
            />
            <span class="truncate">2. Upload Mockups</span>
          </div>

          <!-- Step 3: Upload Digital Files -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              stepStates.upload_files === 'in_progress'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : stepStates.upload_files === 'completed'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : stepStates.upload_files === 'failed'
                    ? 'bg-destructive/10 border-destructive/30 text-destructive font-semibold'
                    : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                stepStates.upload_files === 'in_progress'
                  ? 'lucide:loader-circle'
                  : stepStates.upload_files === 'completed'
                    ? 'lucide:circle-check'
                    : stepStates.upload_files === 'failed'
                      ? 'lucide:circle-alert'
                      : 'lucide:circle'
              "
              :class="[
                'size-4 shrink-0',
                stepStates.upload_files === 'in_progress'
                  ? 'animate-spin text-primary'
                  : stepStates.upload_files === 'completed'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : stepStates.upload_files === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground/40',
              ]"
              aria-hidden="true"
            />
            <span class="truncate">3. Upload Digital Files</span>
          </div>

          <!-- Step 4: Apply Attributes -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              stepStates.apply_attributes === 'in_progress'
                ? 'bg-primary/10 border-primary/30 text-primary font-semibold'
                : stepStates.apply_attributes === 'completed'
                  ? 'bg-secondary border-border text-foreground font-medium'
                  : stepStates.apply_attributes === 'failed'
                    ? 'bg-destructive/10 border-destructive/30 text-destructive font-semibold'
                    : 'bg-background border-border text-muted-foreground',
            ]"
          >
            <Icon
              :name="
                stepStates.apply_attributes === 'in_progress'
                  ? 'lucide:loader-circle'
                  : stepStates.apply_attributes === 'completed'
                    ? 'lucide:circle-check'
                    : stepStates.apply_attributes === 'failed'
                      ? 'lucide:circle-alert'
                      : 'lucide:circle'
              "
              :class="[
                'size-4 shrink-0',
                stepStates.apply_attributes === 'in_progress'
                  ? 'animate-spin text-primary'
                  : stepStates.apply_attributes === 'completed'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : stepStates.apply_attributes === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground/40',
              ]"
              aria-hidden="true"
            />
            <span class="truncate">4. Apply Attributes</span>
          </div>
        </div>
      </div>

      <!-- Completed Success Stats Grid & Actions -->
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
                <Icon
                  :name="copied ? 'lucide:check' : 'lucide:copy'"
                  class="size-3 text-muted-foreground hover:text-foreground"
                  aria-hidden="true"
                />
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
              <span class="truncate">{{ digitalFilesCount > 1 ? `${digitalFilesCount} Real Files Attached` : 'Digital Product Attached' }}</span>
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

        <!-- Post-Dispatch Authoritative Verification Report -->
        <div v-if="listingId" class="pt-2">
          <EtsyDraftVerificationCard
            :workflow-id="workflowId"
            :listing-id="listingId"
            :verification="currentVerification"
            :shop-manager-url="listingManagerUrl"
            @recheck-completed="handleVerificationCompleted"
          />
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
            {{ isDraftRemoved ? 'Create New Etsy Draft' : isGate3Approved ? 'Ready for Draft Creation' : 'Listing Approval Required' }}
          </div>
          <div>
            {{ isDraftRemoved ? 'Generate a new official Etsy draft listing with the approved campaign files.' : isGate3Approved ? 'Creates an official draft listing on your connected Etsy shop with all approved assets.' : 'Approve listing review to authorize and create draft listing on Etsy.' }}
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
