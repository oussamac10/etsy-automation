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
  listing: ListingDraft;
}>();

const emit = defineEmits<{
  (e: 'draft-created'): void;
}>();

const {
  connectionStatus,
  draftStatus,
  isLoading,
  isDispatching,
  errorMessage,
  fetchConnectionStatus,
  triggerCreateEtsyDraft,
  fetchDraftStatus,
} = useEtsy();

let pollInterval: ReturnType<typeof setInterval> | null = null;
const copied = ref(false);

const currentStatus = computed(() => {
  return draftStatus.value?.dispatch_status || props.listing.etsy_dispatch_status || 'not_started';
});

const isCompleted = computed(() => {
  return (
    currentStatus.value === 'completed' ||
    props.workflowState === 'ETSY_DRAFT_CREATED' ||
    Boolean(listingId.value)
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
    props.listing.etsy_failure_reason ||
    'The Etsy dispatch process encountered an issue. Please verify shop connection and retry.'
  );
});

const listingId = computed(() => {
  return draftStatus.value?.etsy_listing_id || props.listing.etsy_listing_id || null;
});

const mockupCount = computed(() => {
  return props.listing.etsy_image_ids?.length || draftStatus.value?.etsy_image_ids?.length || 0;
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
  }
});

onBeforeUnmount(() => {
  stopPolling();
});

watch(currentStatus, (newStatus) => {
  if (['queued', 'creating_listing', 'uploading_images', 'uploading_file'].includes(newStatus)) {
    startPolling();
  } else if (newStatus === 'completed') {
    stopPolling();
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
      emit('draft-created');
    } else if (updated?.dispatch_status === 'failed') {
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
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
    class="shadow-xs border-border transition-all duration-200 overflow-hidden"
    :class="{
      'border-emerald-500/40 bg-linear-to-b from-emerald-50/20 to-transparent dark:from-emerald-950/20': isCompleted,
      'border-primary/40 bg-primary/5': isInProgress,
      'border-destructive/30': isFailed,
    }"
    data-testid="etsy-draft-card"
  >
    <CardHeader class="pb-3 border-b border-border/50 bg-muted/20">
      <div class="flex items-start sm:items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition-colors shadow-2xs"
            :class="[
              isCompleted
                ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30 dark:text-emerald-400'
                : isFailed
                  ? 'bg-destructive/10 text-destructive border-destructive/20'
                  : 'bg-primary/10 text-primary border-primary/20',
            ]"
          >
            <Icon name="lucide:store" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base sm:text-lg flex items-center gap-2 flex-wrap">
              <span>Etsy Listing Dispatch</span>
              <span
                v-if="connectionStatus?.connected && (connectionStatus.shop_name || props.listing.etsy_shop_id)"
                class="inline-flex items-center gap-1.5 px-2 py-0.5 text-2xs font-semibold rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20"
              >
                <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {{ connectionStatus.shop_name || 'Connected Shop' }}
              </span>
            </CardTitle>
            <CardDescription class="text-xs sm:text-sm">
              Creates a private draft listing with master PNG, mockups, and customer download files.
            </CardDescription>
          </div>
        </div>

        <Badge
          v-if="isCompleted"
          variant="success"
          class="gap-1 px-3 py-1 shrink-0 inline-flex items-center shadow-2xs"
          data-testid="etsy-badge-completed"
        >
          <Icon name="lucide:circle-check" class="size-3.5" aria-hidden="true" />
          <span>Draft Created</span>
        </Badge>
        <Badge
          v-else-if="isInProgress"
          variant="warning"
          class="gap-1 px-3 py-1 shrink-0 inline-flex items-center animate-pulse"
          data-testid="etsy-badge-progress"
        >
          <Icon name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
          <span>Dispatching...</span>
        </Badge>
        <Badge
          v-else-if="isFailed"
          variant="destructive"
          class="gap-1 px-3 py-1 shrink-0 inline-flex items-center"
          data-testid="etsy-badge-failed"
        >
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Dispatch Failed</span>
        </Badge>
        <Badge
          v-else
          variant="secondary"
          class="gap-1 px-3 py-1 shrink-0 inline-flex items-center"
          data-testid="etsy-badge-ready"
        >
          <Icon name="lucide:clock-3" class="size-3" aria-hidden="true" />
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
                ? 'bg-primary/10 border-primary/30 text-primary font-medium'
                : currentStatus !== 'queued'
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-300'
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
              :class="['size-4 shrink-0', currentStatus === 'creating_listing' ? 'animate-spin' : '']"
              aria-hidden="true"
            />
            <span>1. Create Listing</span>
          </div>

          <!-- Step 2: Upload Mockups -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              currentStatus === 'uploading_images'
                ? 'bg-primary/10 border-primary/30 text-primary font-medium'
                : ['uploading_file', 'completed'].includes(currentStatus)
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-300'
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
              :class="['size-4 shrink-0', currentStatus === 'uploading_images' ? 'animate-spin' : '']"
              aria-hidden="true"
            />
            <span>2. Upload Mockups</span>
          </div>

          <!-- Step 3: Upload Digital Files -->
          <div
            class="flex items-center gap-2 p-2.5 rounded-lg border transition-colors"
            :class="[
              currentStatus === 'uploading_file'
                ? 'bg-primary/10 border-primary/30 text-primary font-medium'
                : currentStatus === 'completed'
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-300'
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
              :class="['size-4 shrink-0', currentStatus === 'uploading_file' ? 'animate-spin' : '']"
              aria-hidden="true"
            />
            <span>3. Upload Digital Files</span>
          </div>
        </div>
      </div>

      <!-- Completed Success Panel -->
      <div v-if="isCompleted" class="space-y-4" data-testid="etsy-completed-panel">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-card border border-border p-4 rounded-xl text-xs shadow-2xs">
          <!-- Listing ID -->
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Listing ID</span>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="font-mono text-sm font-bold text-foreground">
                {{ listingId || 'N/A' }}
              </span>
              <button
                v-if="listingId"
                type="button"
                class="text-muted-foreground hover:text-foreground cursor-pointer p-0.5"
                title="Copy Listing ID"
                @click="copyListingId"
              >
                <Icon :name="copied ? 'lucide:check' : 'lucide:copy'" class="size-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>

          <!-- Listing State -->
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Listing State</span>
            <span class="inline-flex items-center gap-1 font-semibold text-emerald-700 dark:text-emerald-300 mt-1">
              <Icon name="lucide:shield-check" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              Draft (Safe)
            </span>
          </div>

          <!-- Mockups Count -->
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Mockups Uploaded</span>
            <span class="text-xs font-semibold text-foreground mt-1 block">
              {{ mockupCount }} Mockup Previews
            </span>
          </div>

          <!-- Customer Delivery -->
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Customer Download</span>
            <span class="text-xs font-semibold text-foreground flex items-center gap-1 mt-1">
              <Icon name="lucide:file-archive" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span>Digital ZIP Attached</span>
            </span>
          </div>
        </div>

        <!-- Etsy Guidance & Actions -->
        <div class="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 space-y-3">
          <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div class="flex items-start gap-2.5 text-xs text-muted-foreground">
              <Icon name="lucide:info" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p class="font-medium text-foreground">Where to find this in your Etsy store:</p>
                <p class="mt-0.5">
                  Go to <strong class="text-foreground">Etsy Shop Manager → Listings → Drafts</strong> tab. It is saved in private draft mode so you can review price, shipping, and tags before publishing.
                </p>
              </div>
            </div>

            <div class="flex items-center gap-2 shrink-0">
              <a
                v-if="listingManagerUrl"
                :href="listingManagerUrl"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button
                  variant="default"
                  size="sm"
                  class="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer shadow-xs"
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
                  class="gap-1.5 cursor-pointer text-xs"
                  title="Open all Etsy Draft Listings"
                >
                  <Icon name="lucide:layers" class="size-3.5" aria-hidden="true" />
                  <span>All Drafts</span>
                </Button>
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- Ready to Dispatch Action -->
      <div
        v-else-if="!isInProgress"
        class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1"
      >
        <div class="text-xs text-muted-foreground space-y-0.5">
          <div class="font-semibold text-foreground">Ready for Draft Creation</div>
          <div>Creates an official draft listing on your connected Etsy shop with all approved assets.</div>
        </div>

        <Button
          variant="default"
          size="sm"
          class="gap-2 cursor-pointer shrink-0"
          :disabled="!connectionStatus?.connected || isDispatching"
          data-testid="etsy-create-draft-btn"
          @click="handleCreateDraft"
        >
          <Icon v-if="isDispatching" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:store" class="size-4" aria-hidden="true" />
          <span>Create Etsy Draft</span>
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
