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
import AlertTitle from '~/components/ui/AlertTitle.vue';
import AlertDescription from '~/components/ui/AlertDescription.vue';

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

const currentStatus = computed(() => {
  return draftStatus.value?.dispatch_status || props.listing.etsy_dispatch_status || 'not_started';
});

const isCompleted = computed(() => {
  return currentStatus.value === 'completed' || props.workflowState === 'ETSY_DRAFT_CREATED' || Boolean(props.listing.etsy_listing_id);
});

const isInProgress = computed(() => {
  return ['queued', 'creating_listing', 'uploading_images', 'uploading_file'].includes(currentStatus.value) || isDispatching.value;
});

const isFailed = computed(() => {
  return currentStatus.value === 'failed';
});

const listingManagerUrl = computed(() => {
  const listingId = draftStatus.value?.etsy_listing_id || props.listing.etsy_listing_id;
  if (!listingId) return null;
  return `https://www.etsy.com/your/shops/me/listing-editor/edit/${listingId}`;
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
</script>

<template>
  <Card class="shadow-2xs border-primary/30" data-testid="etsy-draft-card">
    <CardHeader class="pb-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
            <Icon name="lucide:store" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base sm:text-lg">Etsy Listing Dispatch</CardTitle>
            <CardDescription class="text-xs sm:text-sm">
              Publish print-ready master PNG, mockup images, and customer ZIP bundle as a draft
            </CardDescription>
          </div>
        </div>

        <Badge
          v-if="isCompleted"
          variant="success"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-badge-completed"
        >
          <Icon name="lucide:circle-check" class="size-3" aria-hidden="true" />
          <span>Draft Created</span>
        </Badge>
        <Badge
          v-else-if="isInProgress"
          variant="warning"
          class="gap-1 px-3 py-1 inline-flex items-center animate-pulse"
          data-testid="etsy-badge-progress"
        >
          <Icon name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
          <span>Dispatching...</span>
        </Badge>
        <Badge
          v-else-if="isFailed"
          variant="destructive"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-badge-failed"
        >
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Dispatch Failed</span>
        </Badge>
        <Badge
          v-else
          variant="secondary"
          class="gap-1 px-3 py-1 inline-flex items-center"
          data-testid="etsy-badge-ready"
        >
          <Icon name="lucide:clock-3" class="size-3" aria-hidden="true" />
          <span>Ready for Dispatch</span>
        </Badge>
      </div>
    </CardHeader>

    <CardContent class="pt-2 space-y-4">
      <!-- Error Alert -->
      <Alert v-if="errorMessage || (isFailed && listing.etsy_failure_reason)" variant="destructive">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertTitle>Etsy Dispatch Error</AlertTitle>
        <AlertDescription class="flex items-center justify-between">
          <span>{{ errorMessage || listing.etsy_failure_reason }}</span>
          <Button variant="outline" size="sm" class="h-7 text-xs cursor-pointer" @click="handleCreateDraft">
            Retry Dispatch
          </Button>
        </AlertDescription>
      </Alert>

      <!-- Shop Not Connected Notice -->
      <div
        v-if="!connectionStatus?.connected && !isLoading"
        class="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-xs text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
      >
        <div class="flex items-start gap-2.5">
          <Icon name="lucide:triangle-alert" class="size-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" aria-hidden="true" />
          <div>
            <strong class="font-semibold text-foreground block">Etsy Shop Connection Required</strong>
            <span>You must connect your Etsy shop in Settings before creating draft listings.</span>
          </div>
        </div>
        <NuxtLink to="/settings">
          <Button variant="outline" size="sm" class="text-xs h-8 gap-1.5 cursor-pointer shrink-0">
            <Icon name="lucide:settings" class="size-3.5" aria-hidden="true" />
            <span>Open Settings</span>
          </Button>
        </NuxtLink>
      </div>

      <!-- In-Progress Steps Indicator -->
      <div v-if="isInProgress" class="bg-muted/40 border border-border rounded-xl p-4 space-y-3" data-testid="etsy-dispatching-progress">
        <div class="flex items-center justify-between text-xs font-semibold text-foreground">
          <span>Dispatching Draft to Etsy Open API v3...</span>
          <span class="font-mono text-primary animate-pulse">In Progress</span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div class="flex items-center gap-2 p-2 rounded-lg bg-background border border-border">
            <Icon
              :name="currentStatus === 'creating_listing' ? 'lucide:loader-circle' : (currentStatus !== 'queued' ? 'lucide:circle-check' : 'lucide:circle')"
              :class="['size-4 shrink-0', currentStatus === 'creating_listing' ? 'animate-spin text-primary' : (currentStatus !== 'queued' ? 'text-emerald-500' : 'text-muted-foreground')]"
              aria-hidden="true"
            />
            <span>1. Create Listing</span>
          </div>
          <div class="flex items-center gap-2 p-2 rounded-lg bg-background border border-border">
            <Icon
              :name="currentStatus === 'uploading_images' ? 'lucide:loader-circle' : (['uploading_file', 'completed'].includes(currentStatus) ? 'lucide:circle-check' : 'lucide:circle')"
              :class="['size-4 shrink-0', currentStatus === 'uploading_images' ? 'animate-spin text-primary' : (['uploading_file', 'completed'].includes(currentStatus) ? 'text-emerald-500' : 'text-muted-foreground')]"
              aria-hidden="true"
            />
            <span>2. Upload Mockups</span>
          </div>
          <div class="flex items-center gap-2 p-2 rounded-lg bg-background border border-border">
            <Icon
              :name="currentStatus === 'uploading_file' ? 'lucide:loader-circle' : (currentStatus === 'completed' ? 'lucide:circle-check' : 'lucide:circle')"
              :class="['size-4 shrink-0', currentStatus === 'uploading_file' ? 'animate-spin text-primary' : (currentStatus === 'completed' ? 'text-emerald-500' : 'text-muted-foreground')]"
              aria-hidden="true"
            />
            <span>3. Upload Digital ZIP</span>
          </div>
        </div>
      </div>

      <!-- Completed Success Card -->
      <div v-if="isCompleted" class="space-y-4" data-testid="etsy-completed-panel">
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 bg-emerald-500/5 border border-emerald-500/20 p-4 rounded-xl text-xs">
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Listing ID</span>
            <span class="font-mono text-sm font-bold text-foreground">
              {{ listing.etsy_listing_id || draftStatus?.etsy_listing_id || 'N/A' }}
            </span>
          </div>
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Listing State</span>
            <Badge variant="outline" class="text-2xs uppercase tracking-wider font-semibold text-emerald-700 dark:text-emerald-300 mt-0.5">
              Draft (Safe)
            </Badge>
          </div>
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Uploaded Images</span>
            <span class="text-xs font-semibold text-foreground">
              {{ (listing.etsy_image_ids?.length || draftStatus?.etsy_image_ids?.length || 0) }} Mockup Previews
            </span>
          </div>
          <div>
            <span class="text-2xs font-semibold uppercase tracking-wider text-muted-foreground block">Customer Download</span>
            <span class="text-xs font-semibold text-foreground flex items-center gap-1">
              <Icon name="lucide:file-archive" class="size-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span>Digital ZIP Attached</span>
            </span>
          </div>
        </div>

        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1">
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <Icon name="lucide:shield-check" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <span>Listing is safely in draft mode. Review and activate inside Etsy Shop Manager when ready.</span>
          </div>

          <a
            v-if="listingManagerUrl"
            :href="listingManagerUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="shrink-0"
          >
            <Button
              variant="default"
              size="sm"
              class="w-full sm:w-auto gap-2 bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer"
              data-testid="etsy-open-manager-btn"
            >
              <Icon name="lucide:external-link" class="size-3.5" aria-hidden="true" />
              <span>Open in Etsy Shop Manager</span>
            </Button>
          </a>
        </div>
      </div>

      <!-- Ready to Dispatch Action -->
      <div v-else-if="!isInProgress" class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1">
        <div class="text-xs text-muted-foreground space-y-0.5">
          <div class="font-semibold text-foreground">Ready for Draft Creation</div>
          <div>Creates an official draft listing on your connected Etsy shop with all approved assets.</div>
        </div>

        <Button
          variant="default"
          size="sm"
          class="gap-2 cursor-pointer"
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
