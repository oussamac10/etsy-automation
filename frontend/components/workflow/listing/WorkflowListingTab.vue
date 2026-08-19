<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useListing } from '~/composables/useListing';
import ListingEditorCard from './ListingEditorCard.vue';
import TagEditorCard from './TagEditorCard.vue';
import IpRiskCard from './IpRiskCard.vue';
import CustomerPackageCard from './CustomerPackageCard.vue';
import EtsyDraftCard from './EtsyDraftCard.vue';
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
  isBuildingPackage,
  isRestoringVersion,
  isDeletingVersion,
  isDeletingTagHistory,
  isDecidingGate,
  errorMessage,
  loadListing,
  updateListing,
  rescreenTrademark,
  generateSeo,
  buildPackage,
  restoreVersion,
  deleteVersion,
  deleteTagFromHistory,
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

async function handleRestoreVersion(versionNumber: number) {
  successMessage.value = null;
  const draft = await restoreVersion(props.workflowId, versionNumber);
  if (draft) {
    localTitle.value = draft.title;
    localDescription.value = draft.description;
    localTags.value = [...draft.tags];
    successMessage.value = `Successfully restored to Version ${versionNumber}.`;
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleDeleteVersion(versionNumber: number) {
  successMessage.value = null;
  const draft = await deleteVersion(props.workflowId, versionNumber);
  if (draft) {
    successMessage.value = `Version ${versionNumber} removed from history.`;
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleDeleteHistoryTag(tag: string) {
  successMessage.value = null;
  const draft = await deleteTagFromHistory(props.workflowId, tag);
  if (draft) {
    successMessage.value = `Tag "${tag}" removed from campaign history.`;
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleRescreen() {
  successMessage.value = null;
  try {
    if (listingDraft.value && (isListingCopyDirty.value || isTagsDirty.value)) {
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

async function handleBuildPackage() {
  successMessage.value = null;
  const draft = await buildPackage(props.workflowId);
  if (draft) {
    successMessage.value = 'Customer download ZIP package compiled successfully.';
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  }
}

async function handleApprove() {
  successMessage.value = null;
  const draft = await decideGate3(props.workflowId, {
    decision: 'APPROVED',
    acknowledged: warningAcknowledged.value,
  });
  if (draft) {
    emit('approved');
  }
}

async function handleReject() {
  successMessage.value = null;
  const draft = await decideGate3(props.workflowId, {
    decision: 'REJECTED',
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

const isListingCopyDirty = computed(() => {
  if (!listingDraft.value) return false;
  return (
    localTitle.value !== (listingDraft.value.title || '') ||
    localDescription.value !== (listingDraft.value.description || '')
  );
});

const isTagsDirty = computed(() => {
  if (!listingDraft.value) return false;
  const savedTags = listingDraft.value.tags || [];
  if (localTags.value.length !== savedTags.length) return true;
  return JSON.stringify(localTags.value) !== JSON.stringify(savedTags);
});

const isApproved = computed(() => {
  return ['READY_FOR_ETSY_DRAFT', 'ETSY_DRAFT_CREATED', 'PUBLISHED'].includes(props.workflowState);
});
</script>

<template>
  <div class="space-y-6">
    <!-- Feedback Alerts -->
    <Alert
      v-if="errorMessage"
      variant="destructive"
      title="Action Failed"
      :description="errorMessage"
      dismissible
      @dismiss="errorMessage = null"
    />

    <Alert
      v-if="successMessage"
      variant="success"
      title="Success"
      :description="successMessage"
      dismissible
      @dismiss="successMessage = null"
    />

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
            :has-unsaved-changes="isListingCopyDirty"
            :history="listingDraft.history"
            :is-restoring-version="isRestoringVersion"
            :is-deleting-version="isDeletingVersion"
            @update:title="localTitle = $event"
            @update:description="localDescription = $event"
            @save="handleSave"
            @generate-seo="handleGenerateSeo"
            @restore-version="handleRestoreVersion"
            @delete-version="handleDeleteVersion"
          />

          <TagEditorCard
            :tags="localTags"
            :tag-history="listingDraft?.tag_history || []"
            :is-saving="isSaving"
            :is-deleting-tag-history="isDeletingTagHistory"
            :has-unsaved-changes="isTagsDirty"
            @update:tags="localTags = $event"
            @save="handleSave"
            @delete-history-tag="handleDeleteHistoryTag"
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
            :is-building="isBuildingPackage"
            @build-package="handleBuildPackage"
          />

          <!-- Phase 9 Etsy Draft Creation Card (Visible when Gate 3 is Approved or in Draft Dispatch) -->
          <EtsyDraftCard
            v-if="isApproved || ['READY_FOR_ETSY_DRAFT', 'ETSY_DRAFT_CREATED'].includes(workflowState)"
            :workflow-id="workflowId"
            :workflow-state="workflowState"
            :listing="listingDraft"
            @draft-created="loadListingData"
          />
        </div>
      </div>

      <!-- Gate 3 Decision Bar (Only shown when pending human approval) -->
      <div
        v-if="!isApproved"
        class="bg-white/95 backdrop-blur-md border border-border rounded-xl p-3.5 sm:p-4 shadow-md flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 sticky bottom-3 sm:bottom-4 z-10"
      >
        <div class="space-y-0.5 text-center sm:text-left">
          <h3 class="text-sm font-bold text-slate-900 flex items-center justify-center sm:justify-start gap-2">
            <Icon name="lucide:door-open" class="size-4 text-primary" aria-hidden="true" />
            <span>Gate 3: Listing & IP Approval</span>
          </h3>
          <p class="text-xs text-muted-foreground">
            Authorizes this campaign as ready for Etsy draft creation.
          </p>
        </div>

        <div class="flex items-center gap-2 sm:gap-3 justify-stretch sm:justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            :disabled="isDecidingGate"
            class="text-xs h-9 px-3 gap-1.5 cursor-pointer text-muted-foreground hover:text-destructive flex-1 sm:flex-initial justify-center"
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
            class="text-xs h-9 px-4 gap-1.5 opacity-70 cursor-not-allowed flex-1 sm:flex-initial justify-center"
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
            class="text-xs h-9 px-4 gap-1.5 bg-amber-600 hover:bg-amber-700 text-white cursor-pointer flex-1 sm:flex-initial justify-center"
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
            class="text-xs h-9 px-4 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer flex-1 sm:flex-initial justify-center"
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
