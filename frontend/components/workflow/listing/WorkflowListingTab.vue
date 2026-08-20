<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useListing } from '~/composables/useListing';
import ListingEditorCard from './ListingEditorCard.vue';
import TagEditorCard from './TagEditorCard.vue';
import IpRiskCard from './IpRiskCard.vue';
import CategorySelectorCard from './CategorySelectorCard.vue';
import CustomerPackageCard from './CustomerPackageCard.vue';
import PricingInventoryCard from './PricingInventoryCard.vue';
import ShopOrganizationCard from './ShopOrganizationCard.vue';
import TaxonomyAttributesCard from './TaxonomyAttributesCard.vue';
import EtsyDraftCard from './EtsyDraftCard.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import Alert from '~/components/ui/Alert.vue';
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
  isUpdatingTaxonomy,
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
  updateTaxonomy,
} = useListing();

const localTitle = ref('');
const localDescription = ref('');
const localTags = ref<string[]>([]);
const localPriceMinorUnits = ref<number | null>(null);
const localCurrency = ref<string>('USD');
const localQuantity = ref<number>(999);
const localSku = ref<string>('');
const localShopSectionId = ref<string | null>(null);
const localShopSectionName = ref<string | null>(null);
const localShouldAutoRenew = ref<boolean>(false);
const localEtsyProperties = ref<Record<string, any>>({});
const localPrimaryMockupAssetId = ref<string | null>(null);
const localTaxonomyId = ref<number>(6844);
const localTaxonomyPath = ref<string>('Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files');
const warningAcknowledged = ref(false);
const successMessage = ref<string | null>(null);
const showAllReadinessChecks = ref(false);

onMounted(async () => {
  await loadListingData();
});

async function loadListingData() {
  const draft = await loadListing(props.workflowId);
  if (draft) {
    localTitle.value = draft.title || '';
    localDescription.value = draft.description || '';
    localTags.value = [...(draft.tags || [])];
    localPriceMinorUnits.value = draft.price_minor_units ?? 499;
    localCurrency.value = draft.currency || 'USD';
    localQuantity.value = draft.quantity ?? 999;
    localSku.value = draft.sku || '';
    localShopSectionId.value = draft.shop_section_id || null;
    localShopSectionName.value = draft.shop_section_name || null;
    localShouldAutoRenew.value = draft.should_auto_renew ?? false;
    localEtsyProperties.value = draft.etsy_properties ? JSON.parse(JSON.stringify(draft.etsy_properties)) : {};
    localPrimaryMockupAssetId.value = draft.primary_mockup_asset_id || null;
    localTaxonomyId.value = draft.taxonomy_id || 6844;
    localTaxonomyPath.value = draft.taxonomy_path || 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files';
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
      price_minor_units: localPriceMinorUnits.value,
      currency: localCurrency.value,
      quantity: localQuantity.value,
      sku: localSku.value,
      shop_section_id: localShopSectionId.value,
      shop_section_name: localShopSectionName.value,
      should_auto_renew: localShouldAutoRenew.value,
      etsy_properties: localEtsyProperties.value,
      primary_mockup_asset_id: localPrimaryMockupAssetId.value,
      expected_version: listingDraft.value.version,
    });
    if (updated) {
      localTitle.value = updated.title;
      localDescription.value = updated.description;
      localTags.value = [...updated.tags];
      localPriceMinorUnits.value = updated.price_minor_units ?? localPriceMinorUnits.value;
      localCurrency.value = updated.currency || localCurrency.value;
      localQuantity.value = updated.quantity ?? localQuantity.value;
      localSku.value = updated.sku || localSku.value;
      localShopSectionId.value = updated.shop_section_id || null;
      localShopSectionName.value = updated.shop_section_name || null;
      localShouldAutoRenew.value = updated.should_auto_renew ?? false;
      localEtsyProperties.value = updated.etsy_properties ? JSON.parse(JSON.stringify(updated.etsy_properties)) : {};
      localPrimaryMockupAssetId.value = updated.primary_mockup_asset_id || null;
      localTaxonomyId.value = updated.taxonomy_id || localTaxonomyId.value;
      localTaxonomyPath.value = updated.taxonomy_path || localTaxonomyPath.value;
      successMessage.value = 'Listing configuration and metadata saved successfully.';
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

async function handleUpdateCategory(payload: { id: number; path: string }) {
  successMessage.value = null;
  try {
    const updated = await updateTaxonomy(props.workflowId, payload.id, payload.path);
    if (updated) {
      localTaxonomyId.value = updated.taxonomy_id || payload.id;
      localTaxonomyPath.value = updated.taxonomy_path || payload.path;
      successMessage.value = 'Etsy seller category updated successfully.';
      setTimeout(() => {
        successMessage.value = null;
      }, 4000);
    }
  } catch {
    // Error set in composable
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

// Deterministic Readiness Checklist & Blocker Messages (Fixes single source of truth category bug)
const activeTaxonomyId = computed(() => listingDraft.value?.taxonomy_id || localTaxonomyId.value);

const readinessChecks = computed(() => {
  return [
    {
      id: 'title',
      label: 'Title valid (1 - 140 chars)',
      passed: Boolean(localTitle.value.trim() && localTitle.value.length <= 140),
      required: true,
      blockerMsg: 'Listing title is required (max 140 characters).',
    },
    {
      id: 'tags',
      label: 'Exactly 13 tags configured',
      passed: localTags.value.length === 13,
      required: true,
      blockerMsg: 'Etsy requires exactly 13 search tags.',
    },
    {
      id: 'desc',
      label: 'Description present',
      passed: Boolean(localDescription.value.trim()),
      required: true,
      blockerMsg: 'Listing description is required.',
    },
    {
      id: 'category',
      label: 'Etsy seller category selected',
      passed: Boolean(activeTaxonomyId.value),
      required: true,
      blockerMsg: 'Etsy category taxonomy ID is required.',
    },
    {
      id: 'price',
      label: 'Listing price set (> $0.00)',
      passed: Boolean(localPriceMinorUnits.value && localPriceMinorUnits.value > 0),
      required: true,
      blockerMsg: 'Listing price must be configured and greater than zero.',
    },
    {
      id: 'sku',
      label: 'Internal SKU generated',
      passed: Boolean(localSku.value.trim()),
      required: true,
      blockerMsg: 'Internal SKU identifier is required.',
    },
    {
      id: 'ip',
      label: 'IP trademark review clear / acknowledged',
      passed: !isHighRisk.value && (!isWarning.value || warningAcknowledged.value || Boolean(listingDraft.value?.ip_acknowledged_at)),
      required: true,
      blockerMsg: isHighRisk.value
        ? 'High trademark risk detected. Resolve IP matches to proceed.'
        : 'Warning level IP screening requires user acknowledgement.',
    },
  ];
});

const totalPassedChecks = computed(() => readinessChecks.value.filter((c) => c.passed).length);
const totalRequiredChecks = computed(() => readinessChecks.value.filter((c) => c.required).length);

const blockers = computed(() => {
  return readinessChecks.value.filter((c) => c.required && !c.passed).map((c) => c.blockerMsg);
});

const canApprove = computed(() => blockers.value.length === 0);

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

const formattedPriceDisplay = computed(() => {
  if (!localPriceMinorUnits.value) return '€4.99';
  const symbol = localCurrency.value === 'EUR' ? '€' : localCurrency.value === 'GBP' ? '£' : '$';
  return `${symbol}${(localPriceMinorUnits.value / 100).toFixed(2)}`;
});
</script>

<template>
  <div class="space-y-6">
    <!-- Top Header Banner & Compact Status Pills -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 sm:p-5 rounded-xl bg-card border border-border shadow-xs">
      <div class="space-y-1">
        <h2 class="text-base font-bold text-foreground flex items-center gap-2">
          <Icon name="lucide:check-square" class="size-5 text-primary" aria-hidden="true" />
          <span>Prepare your Etsy draft</span>
        </h2>
        <p class="text-xs text-muted-foreground">
          Review search metadata, Etsy settings, IP screening and buyer delivery before creating the Etsy draft.
        </p>
      </div>

      <!-- Compact Status Pills -->
      <div v-if="listingDraft" class="flex flex-wrap items-center gap-2">
        <Badge variant="outline" class="text-xs py-1 px-2.5 gap-1.5 font-normal bg-muted/40 shrink-0">
          <Icon name="lucide:tags" class="size-3.5 text-primary" aria-hidden="true" />
          <span>SEO: {{ localTags.length }}/13</span>
        </Badge>

        <Badge variant="outline" class="text-xs py-1 px-2.5 gap-1.5 font-normal bg-muted/40 shrink-0">
          <Icon name="lucide:folder-tree" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>Category: Ready</span>
        </Badge>

        <Badge variant="outline" class="text-xs py-1 px-2.5 gap-1.5 font-normal bg-muted/40 shrink-0">
          <Icon name="lucide:tag" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>Price: {{ formattedPriceDisplay }}</span>
        </Badge>

        <Badge
          variant="outline"
          class="text-xs py-1 px-2.5 gap-1.5 font-normal shrink-0"
          :class="isHighRisk ? 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20' : isWarning ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'"
        >
          <Icon name="lucide:shield-check" class="size-3.5" aria-hidden="true" />
          <span>IP: {{ riskLevel.toUpperCase() }}</span>
        </Badge>

        <Badge
          variant="outline"
          class="text-xs py-1 px-2.5 gap-1.5 font-medium shrink-0"
          :class="canApprove ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'"
        >
          <Icon :name="canApprove ? 'lucide:check-circle-2' : 'lucide:alert-circle'" class="size-3.5" aria-hidden="true" />
          <span>Readiness: {{ totalPassedChecks }}/{{ totalRequiredChecks }}</span>
        </Badge>
      </div>
    </div>

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

    <!-- Main Content Grid with Independent Main and Sidebar Columns (Zero Whitespace Gaps) -->
    <div v-else-if="listingDraft" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <!-- Main Column (~65-70% = 8 cols on desktop): Grouped Listing Content, Etsy Classification, Pricing & Organization -->
        <main class="lg:col-span-8 space-y-6">
          <!-- Section 1: Listing Content -->
          <div class="space-y-4">
            <div class="flex items-center gap-2 text-xs font-bold text-foreground uppercase tracking-wider px-1">
              <Icon name="lucide:file-text" class="size-4 text-primary" aria-hidden="true" />
              <span>Listing Content</span>
            </div>

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

          <!-- Section 2: Etsy Classification -->
          <div class="space-y-4 pt-2">
            <div class="flex items-center gap-2 text-xs font-bold text-foreground uppercase tracking-wider px-1">
              <Icon name="lucide:folder-tree" class="size-4 text-primary" aria-hidden="true" />
              <span>Etsy Classification</span>
            </div>

            <CategorySelectorCard
              :workflow-id="workflowId"
              :taxonomy-id="activeTaxonomyId"
              :taxonomy-path="localTaxonomyPath"
              :is-updating="isUpdatingTaxonomy"
              @update-category="handleUpdateCategory"
            />

            <TaxonomyAttributesCard
              :workflow-id="workflowId"
              :taxonomy-id="activeTaxonomyId"
              :etsy-properties="localEtsyProperties"
              :is-saving="isSaving"
              @update:etsy-properties="localEtsyProperties = $event"
              @save="handleSave"
            />
          </div>

          <!-- Section 3: Pricing & Organization -->
          <div class="space-y-4 pt-2">
            <div class="flex items-center gap-2 text-xs font-bold text-foreground uppercase tracking-wider px-1">
              <Icon name="lucide:tag" class="size-4 text-primary" aria-hidden="true" />
              <span>Pricing &amp; Organization</span>
            </div>

            <PricingInventoryCard
              :workflow-id="workflowId"
              :price-minor-units="localPriceMinorUnits"
              :currency="localCurrency"
              :quantity="localQuantity"
              :sku="localSku"
              :is-saving="isSaving"
              @update:price-minor-units="localPriceMinorUnits = $event"
              @update:currency="localCurrency = $event"
              @update:quantity="localQuantity = $event"
              @update:sku="localSku = $event"
              @save="handleSave"
            />

            <ShopOrganizationCard
              :workflow-id="workflowId"
              :shop-section-id="localShopSectionId"
              :shop-section-name="localShopSectionName"
              :should-auto-renew="localShouldAutoRenew"
              :is-saving="isSaving"
              @update:shop-section-id="localShopSectionId = $event"
              @update:shop-section-name="localShopSectionName = $event"
              @update:should-auto-renew="localShouldAutoRenew = $event"
              @save="handleSave"
            />
          </div>
        </main>

        <!-- Right Sidebar (~30-35% = 4 cols on desktop): Flowing independently (Order: 1. Readiness -> 2. IP -> 3. Delivery -> 4. Etsy Draft) -->
        <aside class="lg:col-span-4 space-y-6">
          <!-- Compact Review Status / Readiness Checklist Card -->
          <div class="p-4 rounded-xl bg-card border border-border shadow-xs space-y-3" data-testid="readiness-summary-card">
            <div class="flex items-center justify-between">
              <h3 class="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-1.5">
                <Icon name="lucide:clipboard-check" class="size-4 text-primary" aria-hidden="true" />
                <span>Review Status</span>
              </h3>
              <Badge variant="outline" class="text-[10px] font-mono font-semibold" :class="canApprove ? 'text-emerald-700 bg-emerald-500/10 border-emerald-500/20' : 'text-amber-700 bg-amber-500/10 border-amber-500/20'">
                {{ totalPassedChecks }}/{{ totalRequiredChecks }} Ready
              </Badge>
            </div>

            <!-- Compact Collapsed Summary -->
            <div class="p-2.5 rounded-lg bg-muted/40 border border-border text-xs space-y-1">
              <p class="font-semibold text-foreground flex items-center gap-1.5">
                <Icon :name="canApprove ? 'lucide:check-circle-2' : 'lucide:alert-circle'" class="size-3.5" :class="canApprove ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'" aria-hidden="true" />
                <span>{{ canApprove ? 'All required checks complete' : `${blockers.length} item${blockers.length > 1 ? 's' : ''} need attention` }}</span>
              </p>
              <p v-if="!canApprove" class="text-[11px] text-muted-foreground">
                {{ blockers[0] }}
              </p>
              <button
                type="button"
                class="text-[11px] font-medium text-primary hover:underline pt-1 cursor-pointer"
                @click="showAllReadinessChecks = !showAllReadinessChecks"
              >
                {{ showAllReadinessChecks ? 'Hide checks' : 'View all checks' }}
              </button>
            </div>

            <!-- Detailed Checks List (when expanded) -->
            <div v-if="showAllReadinessChecks" class="space-y-1.5 text-xs pt-1 border-t border-border/50">
              <div
                v-for="check in readinessChecks"
                :key="check.id"
                class="flex items-center justify-between py-1 px-2 rounded border text-xs"
                :class="check.passed ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-900 dark:text-emerald-200' : 'bg-muted/40 border-border text-muted-foreground'"
              >
                <span class="flex items-center gap-2 truncate">
                  <Icon
                    :name="check.passed ? 'lucide:check-circle-2' : 'lucide:circle'"
                    class="size-3.5 shrink-0"
                    :class="check.passed ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'"
                    aria-hidden="true"
                  />
                  <span class="truncate">{{ check.label }}</span>
                </span>
                <Badge v-if="!check.passed" variant="outline" class="text-[9px] px-1 py-0 h-4 text-amber-700 bg-amber-500/10 border-amber-500/20 shrink-0">
                  Required
                </Badge>
              </div>
            </div>
          </div>

          <!-- Card 2: Trademark / IP Risk -->
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

          <!-- Card 3: Buyer Delivery Package -->
          <CustomerPackageCard
            :package-asset="listingDraft.package_asset"
            :download-url="listingDraft.package_download_url"
            :version="listingDraft.version"
            :is-building="isBuildingPackage"
            @build-package="handleBuildPackage"
          />

          <!-- Card 4: Etsy Draft State Machine Card -->
          <EtsyDraftCard
            :workflow-id="workflowId"
            :workflow-state="workflowState"
            :listing="listingDraft"
          />
        </aside>
      </div>

      <!-- Sticky Gate 3 Decision Bar -->
      <div
        v-if="!isApproved"
        class="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-border rounded-xl p-3.5 sm:p-4 shadow-lg flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 sticky bottom-3 sm:bottom-4 z-10"
      >
        <div class="space-y-1 text-center sm:text-left min-w-0">
          <h3 class="text-sm font-bold text-foreground flex items-center justify-center sm:justify-start gap-2">
            <Icon name="lucide:door-open" class="size-4 text-primary" aria-hidden="true" />
            <span>Gate 3: Listing &amp; IP Approval</span>
          </h3>
          <p v-if="canApprove" class="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
            ✓ All checks passed. Ready to approve for Etsy draft creation.
          </p>
          <p v-else class="text-xs text-amber-600 dark:text-amber-400 font-medium">
            ⚠ {{ blockers.length }} issue{{ blockers.length > 1 ? 's' : '' }} need attention: {{ blockers[0] }}
          </p>
        </div>

        <div class="flex items-center gap-2 sm:gap-3 justify-stretch sm:justify-end shrink-0">
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
            <span>Approve for Etsy Draft (Warning)</span>
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
            <span>{{ isApproved ? 'Approved' : 'Approve for Etsy Draft' }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
