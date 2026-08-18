<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useListing } from '~/composables/useListing';
import ListingEditorCard from './ListingEditorCard.vue';
import TagEditorCard from './TagEditorCard.vue';
import IpRiskCard from './IpRiskCard.vue';
import CustomerPackageCard from './CustomerPackageCard.vue';
import Button from '~/components/ui/Button.vue';
import Alert from '~/components/ui/Alert.vue';
import AlertTitle from '~/components/ui/AlertTitle.vue';
import AlertDescription from '~/components/ui/AlertDescription.vue';
import type { RiskLevel } from '~/types/listing';

const props = defineProps<{
  workflowId: string;
  workflowState: string;
}>();

const emit = defineEmits<{
  (e: 'approved'): void;
  (e: 'rejected'): void;
}>();

const {
  listingDraft,
  isLoading,
  isSaving,
  isScreening,
  isGeneratingSeo,
  isDecidingGate,
  errorMessage,
  loadListing,
  updateListing,
  rescreenTrademark,
  generateSeo,
  decideGate3,
} = useListing();

const localTitle = ref('');
const localDescription = ref('');
const localTags = ref<string[]>([]);
const warningAcknowledged = ref(false);
const successMessage = ref<string | null>(null);

onMounted(async () => {
  await loadListingData();
});

async function loadListingData() {
  const draft = await loadListing(props.workflowId);
  if (draft) {
    localTitle.value = draft.title || '';
    localDescription.value = draft.description || '';
    localTags.value = [...(draft.tags || [])];
    warningAcknowledged.value = draft.ip_acknowledged_at !== null && draft.ip_acknowledged_at !== undefined;
  }
}

async function handleSave() {
  if (!listingDraft.value) return;
  successMessage.value = null;

  try {
    const updated = await updateListing(props.workflowId, {
      title: localTitle.value,
      description: localDescription.value,
      tags: localTags.value,
      expected_version: listingDraft.value.version,
    });
    if (updated) {
      localTitle.value = updated.title;
      localDescription.value = updated.description;
      localTags.value = [...updated.tags];
      successMessage.value = 'Listing changes saved and trademark screening updated.';
      setTimeout(() => {
        successMessage.value = null;
      }, 4000);
    }
  } catch {
    // Error set in composable
  }
}

async function handleGenerateSeo() {
  successMessage.value = null;
  const draft = await generateSeo(props.workflowId);
  if (draft) {
    localTitle.value = draft.title;
    localDescription.value = draft.description;
    localTags.value = [...draft.tags];
    successMessage.value = 'New SEO copy and tags generated successfully.';
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleRescreen() {
  successMessage.value = null;
  try {
    if (listingDraft.value) {
      await updateListing(props.workflowId, {
        title: localTitle.value,
        description: localDescription.value,
        tags: localTags.value,
        expected_version: listingDraft.value.version,
      });
    }
  } catch {
    // Proceed with rescreen
  }

  const draft = await rescreenTrademark(props.workflowId);
  if (draft) {
    localTitle.value = draft.title;
    localDescription.value = draft.description;
    localTags.value = [...draft.tags];
    successMessage.value = 'Trademark screening updated with fresh registry data.';
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleApprove() {
  successMessage.value = null;
  const draft = await decideGate3(props.workflowId, {
    decision: 'approved',
    acknowledged: warningAcknowledged.value,
  });
  if (draft) {
    emit('approved');
  }
}

async function handleReject() {
  successMessage.value = null;
  const draft = await decideGate3(props.workflowId, {
    decision: 'rejected',
    acknowledged: false,
  });
  if (draft) {
    emit('rejected');
  }
}

const riskLevel = computed<RiskLevel>(() => {
  return listingDraft.value?.ip_risk_level || 'unknown';
});

const isHighRisk = computed(() => riskLevel.value === 'high');
const isWarning = computed(() => riskLevel.value === 'medium');

const canApprove = computed(() => {
  if (isHighRisk.value) return false;
  if (localTags.value.length !== 13) return false;
  if (!localTitle.value.trim() || localTitle.value.length > 140) return false;
  if (isWarning.value && !warningAcknowledged.value && !listingDraft.value?.ip_acknowledged_at) return false;
  return true;
});

const isApproved = computed(() => {
  return ['READY_FOR_ETSY_DRAFT', 'PUBLISHED'].includes(props.workflowState);
});
</script>

<template>
  <div class="space-y-6">
    <!-- Feedback Alerts -->
    <Alert v-if="errorMessage" variant="destructive" class="border-destructive/40">
      <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
      <AlertTitle>Action Failed</AlertTitle>
      <AlertDescription>{{ errorMessage }}</AlertDescription>
    </Alert>

    <Alert v-if="successMessage" variant="success" class="border-emerald-200 bg-emerald-50 text-emerald-900">
      <Icon name="lucide:circle-check" class="size-4 text-emerald-600" aria-hidden="true" />
      <AlertTitle>Success</AlertTitle>
      <AlertDescription>{{ successMessage }}</AlertDescription>
    </Alert>

    <!-- Loading Skeleton -->
    <div v-if="isLoading && !listingDraft" class="space-y-4">
      <div class="h-48 bg-slate-100 animate-pulse rounded-xl" />
      <div class="h-36 bg-slate-100 animate-pulse rounded-xl" />
    </div>

    <!-- Main Content Grid -->
    <div v-else-if="listingDraft" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <!-- Left Column: Copy & Tags -->
        <div class="space-y-6">
          <ListingEditorCard
            :title="localTitle"
            :description="localDescription"
            :ai-disclosure="listingDraft.ai_disclosure"
            :version="listingDraft.version"
            :is-saving="isSaving"
            :is-generating-seo="isGeneratingSeo"
            @update:title="localTitle = $event"
            @update:description="localDescription = $event"
            @save="handleSave"
            @generate-seo="handleGenerateSeo"
          />

          <TagEditorCard
            :tags="localTags"
            :is-saving="isSaving"
            @update:tags="localTags = $event"
            @save="handleSave"
          />
        </div>

        <!-- Right Column: IP Risk & Customer ZIP Package -->
        <div class="space-y-6">
          <IpRiskCard
            :risk-level="riskLevel"
            :findings="listingDraft.ip_findings"
            :acknowledged-at="listingDraft.ip_acknowledged_at"
            :acknowledged-by="listingDraft.ip_acknowledged_by"
            :warning-acknowledged="warningAcknowledged"
            :is-screening="isScreening"
            @update:warning-acknowledged="warningAcknowledged = $event"
            @rescreen="handleRescreen"
          />

          <CustomerPackageCard
            :package-asset="listingDraft.package_asset"
            :download-url="listingDraft.package_download_url"
            :version="listingDraft.version"
          />
        </div>
      </div>

      <!-- Gate 3 Decision Bar -->
      <div class="bg-white border border-border rounded-xl p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4 sticky bottom-4 z-10 backdrop-blur-md">
        <div class="space-y-0.5 text-center sm:text-left">
          <h3 class="text-sm font-bold text-slate-900 flex items-center justify-center sm:justify-start gap-2">
            <Icon name="lucide:door-open" class="size-4 text-primary" aria-hidden="true" />
            <span>Gate 3: Listing & IP Approval</span>
          </h3>
          <p class="text-xs text-muted-foreground">
            Authorizes this campaign as ready for Etsy draft creation. No auto-publishing.
          </p>
        </div>

        <div class="flex items-center gap-2 sm:gap-3 flex-wrap justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            :disabled="isDecidingGate"
            class="text-xs h-8 sm:h-9 px-2.5 sm:px-3.5 gap-1.5 cursor-pointer text-muted-foreground hover:text-destructive shrink-0"
            @click="handleReject"
          >
            <Icon name="lucide:x-circle" class="size-4" aria-hidden="true" />
            <span>Reject</span>
          </Button>

          <!-- High Risk Blocked Button -->
          <Button
            v-if="isHighRisk"
            type="button"
            variant="destructive"
            size="sm"
            disabled
            class="text-xs h-8 sm:h-9 px-3 sm:px-4 gap-1.5 opacity-70 cursor-not-allowed shrink-0"
          >
            <Icon name="lucide:shield-ban" class="size-4" aria-hidden="true" />
            <span>Approval Blocked</span>
          </Button>

          <!-- Warning Button -->
          <Button
            v-else-if="isWarning"
            type="button"
            variant="default"
            size="sm"
            :disabled="!canApprove || isDecidingGate"
            class="text-xs h-8 sm:h-9 px-3 sm:px-4 gap-1.5 bg-amber-600 hover:bg-amber-700 text-white cursor-pointer shrink-0"
            @click="handleApprove"
          >
            <Icon v-if="isDecidingGate" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:check-circle-2" class="size-4" aria-hidden="true" />
            <span>Approve (Warning)</span>
          </Button>

          <!-- Standard Cleared / Approved Button -->
          <Button
            v-else
            type="button"
            variant="default"
            size="sm"
            :disabled="!canApprove || isDecidingGate"
            class="text-xs h-8 sm:h-9 px-3 sm:px-4 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer shrink-0"
            @click="handleApprove"
          >
            <Icon v-if="isDecidingGate" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
            <Icon v-else-if="isApproved" name="lucide:badge-check" class="size-4" aria-hidden="true" />
            <Icon v-else name="lucide:check-circle-2" class="size-4" aria-hidden="true" />
            <span>{{ isApproved ? 'Approved' : 'Approve for Etsy' }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
