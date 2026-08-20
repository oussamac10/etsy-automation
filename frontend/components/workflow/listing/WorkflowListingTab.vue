<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useListing } from '~/composables/useListing';
import { generateFrontendSku } from '~/utils/sku';
import ListingEditorCard from './ListingEditorCard.vue';
import TagEditorCard from './TagEditorCard.vue';
import IpRiskCard from './IpRiskCard.vue';
import CategorySelectorCard from './CategorySelectorCard.vue';
import CustomerPackageCard from './CustomerPackageCard.vue';
import PricingInventoryCard from './PricingInventoryCard.vue';
import ShopOrganizationCard from './ShopOrganizationCard.vue';
import TaxonomyAttributesCard from './TaxonomyAttributesCard.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Alert from '~/components/ui/Alert.vue';
import type { RiskLevel } from '~/types/listing';

type SubTabKey = 'content' | 'etsy-details' | 'ip-compliance' | 'delivery' | 'final-review';

const props = defineProps<{
  workflowId: string;
  workflowState: string;
}>();

const emit = defineEmits<{
  (e: 'approved'): void;
  (e: 'rejected'): void;
}>();

const route = useRoute();
const router = useRouter();

const activeSubTab = ref<SubTabKey>(
  (route?.query?.review as SubTabKey) || 'content'
);

watch(
  () => route?.query?.review,
  (newVal) => {
    if (newVal && ['content', 'etsy-details', 'ip-compliance', 'delivery', 'final-review'].includes(newVal as string)) {
      activeSubTab.value = newVal as SubTabKey;
    }
  }
);

function setActiveSubTab(tab: SubTabKey) {
  activeSubTab.value = tab;
  try {
    if (router && route) {
      router.replace({
        query: {
          ...route.query,
          review: tab,
        },
      });
    }
  } catch {
    // Navigation fallback
  }
}

const {
  listingDraft,
  taxonomyProperties,
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
  fetchTaxonomyProperties,
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
const categorySelectorRef = ref<{ openModal: () => void; loadFitness: () => Promise<void> } | null>(null);

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
    localSku.value = draft.sku || generateFrontendSku(draft.title, props.workflowId);
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

const activeTaxonomyId = computed(() => listingDraft.value?.taxonomy_id || localTaxonomyId.value);

// Sub-Tab Readiness & Validation
const isContentReady = computed(() => {
  return Boolean(
    localTitle.value.trim() &&
    localTitle.value.length <= 140 &&
    localDescription.value.trim() &&
    localTags.value.length === 13
  );
});

const missingRequiredProperties = computed(() => {
  if (!taxonomyProperties.value || taxonomyProperties.value.length === 0) return [];
  const saved = localEtsyProperties.value || {};
  const missing: string[] = [];
  for (const prop of taxonomyProperties.value) {
    if (prop.is_required) {
      const entry = saved[String(prop.property_id)];
      if (!entry || !entry.values || entry.values.length === 0) {
        missing.push(prop.name);
      }
    }
  }
  return missing;
});

const isEtsyDetailsReady = computed(() => {
  return Boolean(
    activeTaxonomyId.value &&
    localPriceMinorUnits.value &&
    localPriceMinorUnits.value > 0 &&
    missingRequiredProperties.value.length === 0
  );
});

const isIpReady = computed(() => {
  return !isHighRisk.value && (!isWarning.value || warningAcknowledged.value || Boolean(listingDraft.value?.ip_acknowledged_at));
});

const isDeliveryReady = computed(() => {
  return Boolean(listingDraft.value?.package_asset);
});

// Centralized Readiness Checks
const readinessChecks = computed(() => {
  return [
    {
      id: 'title',
      label: 'Title valid (1 - 140 chars)',
      tab: 'content' as SubTabKey,
      passed: Boolean(localTitle.value.trim() && localTitle.value.length <= 140),
      required: true,
      blockerMsg: 'Listing title is required (max 140 characters).',
    },
    {
      id: 'tags',
      label: 'Exactly 13 tags configured',
      tab: 'content' as SubTabKey,
      passed: localTags.value.length === 13,
      required: true,
      blockerMsg: 'Etsy requires exactly 13 search tags.',
    },
    {
      id: 'desc',
      label: 'Description present',
      tab: 'content' as SubTabKey,
      passed: Boolean(localDescription.value.trim()),
      required: true,
      blockerMsg: 'Listing description is required.',
    },
    {
      id: 'category',
      label: 'Etsy seller category selected',
      tab: 'etsy-details' as SubTabKey,
      passed: Boolean(activeTaxonomyId.value),
      required: true,
      blockerMsg: 'Etsy category taxonomy ID is required.',
    },
    {
      id: 'category-attributes',
      label: missingRequiredProperties.value.length === 0
        ? 'Category attributes valid'
        : `${missingRequiredProperties.value.length} required attribute${missingRequiredProperties.value.length > 1 ? 's' : ''} missing`,
      tab: 'etsy-details' as SubTabKey,
      passed: missingRequiredProperties.value.length === 0,
      required: true,
      blockerMsg: missingRequiredProperties.value.length > 0
        ? `Required Etsy category attributes missing: ${missingRequiredProperties.value.join(', ')}.`
        : '',
    },
    {
      id: 'price',
      label: 'Listing price configured (> $0.00)',
      tab: 'etsy-details' as SubTabKey,
      passed: Boolean(localPriceMinorUnits.value && localPriceMinorUnits.value > 0),
      required: true,
      blockerMsg: 'Listing price must be configured and greater than zero.',
    },
    {
      id: 'sku',
      label: 'Internal SKU generated',
      tab: 'etsy-details' as SubTabKey,
      passed: Boolean(localSku.value.trim()),
      required: true,
      blockerMsg: 'Internal SKU identifier is required.',
    },
    {
      id: 'ip',
      label: 'IP trademark review clear / acknowledged',
      tab: 'ip-compliance' as SubTabKey,
      passed: isIpReady.value,
      required: true,
      blockerMsg: isHighRisk.value
        ? 'High trademark risk detected. Resolve IP matches to proceed.'
        : 'Warning level IP screening requires user acknowledgement.',
    },
    {
      id: 'delivery',
      label: 'Buyer download package compiled',
      tab: 'delivery' as SubTabKey,
      passed: isDeliveryReady.value,
      required: false,
      blockerMsg: 'Customer delivery ZIP package is not built.',
    },
  ];
});

const totalPassedChecks = computed(() => readinessChecks.value.filter((c) => c.passed && c.required).length);
const totalRequiredChecks = computed(() => readinessChecks.value.filter((c) => c.required).length);

const blockers = computed(() => {
  return readinessChecks.value.filter((c) => c.required && !c.passed);
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

const isPricingDirty = computed(() => {
  if (!listingDraft.value) return false;
  return (
    localPriceMinorUnits.value !== (listingDraft.value.price_minor_units ?? 499) ||
    localCurrency.value !== (listingDraft.value.currency || 'USD') ||
    localQuantity.value !== (listingDraft.value.quantity ?? 999) ||
    localSku.value.trim() !== (listingDraft.value.sku || '').trim()
  );
});

const isShopOrgDirty = computed(() => {
  if (!listingDraft.value) return false;
  return (
    localShopSectionId.value !== (listingDraft.value.shop_section_id || null) ||
    localShopSectionName.value !== (listingDraft.value.shop_section_name || null) ||
    localShouldAutoRenew.value !== (listingDraft.value.should_auto_renew ?? false)
  );
});

const isApproved = computed(() => {
  return ['READY_FOR_ETSY_DRAFT', 'ETSY_DRAFT_CREATED', 'PUBLISHED'].includes(props.workflowState);
});

const formattedPriceDisplay = computed(() => {
  if (!localPriceMinorUnits.value) return '$4.99';
  const symbol = localCurrency.value === 'EUR' ? '€' : localCurrency.value === 'GBP' ? '£' : '$';
  return `${symbol}${(localPriceMinorUnits.value / 100).toFixed(2)}`;
});

const subTabs = computed(() => [
  {
    key: 'content' as SubTabKey,
    label: 'Listing Content',
    icon: 'lucide:file-text',
    isReady: isContentReady.value,
    badgeText: isContentReady.value ? 'Ready' : 'Needs attention',
  },
  {
    key: 'etsy-details' as SubTabKey,
    label: 'Etsy Details',
    icon: 'lucide:store',
    isReady: isEtsyDetailsReady.value,
    badgeText: isEtsyDetailsReady.value ? 'Ready' : 'Needs attention',
  },
  {
    key: 'ip-compliance' as SubTabKey,
    label: 'IP & Compliance',
    icon: 'lucide:shield-check',
    isReady: isIpReady.value,
    badgeText: isHighRisk.value ? 'Blocked' : isWarning.value ? 'Warning' : 'Low Risk',
  },
  {
    key: 'delivery' as SubTabKey,
    label: 'Buyer Delivery',
    icon: 'lucide:package-check',
    isReady: isDeliveryReady.value,
    badgeText: isDeliveryReady.value ? 'Ready' : 'Needs Build',
  },
  {
    key: 'final-review' as SubTabKey,
    label: 'Final Review',
    icon: 'lucide:clipboard-check',
    isReady: canApprove.value,
    badgeText: canApprove.value ? `${totalPassedChecks.value}/${totalRequiredChecks.value}` : `${blockers.value.length} issues`,
  },
]);
</script>

<template>
  <div class="space-y-6" data-testid="workflow-listing-tab">
    <!-- Top-Level Step 4 Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-xl bg-card border border-border shadow-xs">
      <div class="space-y-1">
        <h2 class="text-base sm:text-lg font-bold text-foreground flex items-center gap-2">
          <Icon name="lucide:check-square" class="size-5 text-primary" aria-hidden="true" />
          <span>Listing &amp; IP Review</span>
        </h2>
        <p class="text-xs text-muted-foreground">
          Prepare and verify your Etsy listing before draft creation.
        </p>
      </div>

      <!-- Quick Summary Badges -->
      <div v-if="listingDraft" class="flex flex-wrap items-center gap-2">
        <Badge variant="outline" class="text-xs py-1 px-2.5 gap-1.5 font-normal bg-muted/40 shrink-0">
          <Icon name="lucide:tags" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Tags: {{ localTags.length }}/13</span>
        </Badge>

        <Badge variant="outline" class="text-xs py-1 px-2.5 gap-1.5 font-normal bg-muted/40 shrink-0">
          <Icon name="lucide:tag" class="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>{{ formattedPriceDisplay }}</span>
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

    <!-- Secondary Internal Navigation (5 Sub-Tabs) -->
    <div class="flex items-center gap-1.5 sm:gap-2 p-1.5 rounded-xl bg-muted/60 border border-border overflow-x-auto scrollbar-none" role="tablist" aria-label="Listing Preparation Steps">
      <button
        v-for="tab in subTabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeSubTab === tab.key"
        class="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer select-none"
        :class="
          activeSubTab === tab.key
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-semibold'
            : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
        "
        @click="setActiveSubTab(tab.key)"
      >
        <Icon :name="tab.icon" class="size-3.5 shrink-0" :class="activeSubTab === tab.key ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
        <span>{{ tab.label }}</span>
        <span
          class="size-1.5 rounded-full shrink-0"
          :class="tab.isReady ? 'bg-emerald-500' : 'bg-amber-500'"
        />
      </button>
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

    <!-- Sub-Tab Content Views -->
    <div v-else-if="listingDraft" class="space-y-6">
      <!-- ================================================== -->
      <!-- SUB-TAB 1: LISTING CONTENT                         -->
      <!-- ================================================== -->
      <section v-if="activeSubTab === 'content'" class="space-y-6" data-testid="subtab-content">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-border/50">
          <div>
            <h3 class="text-sm font-bold text-foreground">Listing Content</h3>
            <p class="text-xs text-muted-foreground">
              Prepare the title, description and search tags shoppers will see on Etsy.
            </p>
          </div>
          <Badge
            variant="outline"
            class="self-start sm:self-auto text-xs font-mono"
            :class="isContentReady ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'"
          >
            {{ isContentReady ? 'Ready' : 'Needs attention' }}
          </Badge>
        </div>

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
      </section>

      <!-- ================================================== -->
      <!-- SUB-TAB 2: ETSY DETAILS                            -->
      <!-- ================================================== -->
      <section v-else-if="activeSubTab === 'etsy-details'" class="space-y-6" data-testid="subtab-etsy-details">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-border/50">
          <div>
            <h3 class="text-sm font-bold text-foreground">Etsy Details &amp; Classification</h3>
            <p class="text-xs text-muted-foreground">
              Configure how Etsy classifies, prices, and categorizes your digital listing.
            </p>
          </div>
          <Badge
            variant="outline"
            class="self-start sm:self-auto text-xs font-mono"
            :class="isEtsyDetailsReady ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'"
          >
            {{ isEtsyDetailsReady ? 'Ready' : 'Needs attention' }}
          </Badge>
        </div>

        <!-- 2 Independent Columns on Desktop (No Grid Row Couplings) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <!-- Left Column (Category & Attributes) -->
          <div class="lg:col-span-6 space-y-6">
            <CategorySelectorCard
              ref="categorySelectorRef"
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
              @review-category="categorySelectorRef?.openModal()"
            />
          </div>

          <!-- Right Column (Pricing & Organization) -->
          <div class="lg:col-span-6 space-y-6">
            <PricingInventoryCard
              :workflow-id="workflowId"
              :title="localTitle"
              :price-minor-units="localPriceMinorUnits"
              :currency="localCurrency"
              :quantity="localQuantity"
              :sku="localSku"
              :has-unsaved-changes="isPricingDirty"
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
              :has-unsaved-changes="isShopOrgDirty"
              :is-saving="isSaving"
              @update:shop-section-id="localShopSectionId = $event"
              @update:shop-section-name="localShopSectionName = $event"
              @update:should-auto-renew="localShouldAutoRenew = $event"
              @save="handleSave"
            />
          </div>
        </div>
      </section>

      <!-- ================================================== -->
      <!-- SUB-TAB 3: IP & COMPLIANCE                         -->
      <!-- ================================================== -->
      <section v-else-if="activeSubTab === 'ip-compliance'" class="space-y-6" data-testid="subtab-ip-compliance">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-border/50">
          <div>
            <h3 class="text-sm font-bold text-foreground">IP &amp; Trademark Compliance</h3>
            <p class="text-xs text-muted-foreground">
              Review USPTO trademark screening and compliance clearance before approval.
            </p>
          </div>
          <Badge
            variant="outline"
            class="self-start sm:self-auto text-xs font-mono"
            :class="isHighRisk ? 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20' : isWarning ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'"
          >
            {{ riskLevel.toUpperCase() }} RISK
          </Badge>
        </div>

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
      </section>

      <!-- ================================================== -->
      <!-- SUB-TAB 4: BUYER DELIVERY                          -->
      <!-- ================================================== -->
      <section v-else-if="activeSubTab === 'delivery'" class="space-y-6" data-testid="subtab-delivery">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-border/50">
          <div>
            <h3 class="text-sm font-bold text-foreground">Buyer Delivery Package</h3>
            <p class="text-xs text-muted-foreground">
              Review exactly what files the Etsy buyer will receive upon purchase.
            </p>
          </div>
          <Badge
            variant="outline"
            class="self-start sm:self-auto text-xs font-mono"
            :class="isDeliveryReady ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' : 'bg-muted text-muted-foreground border-border'"
          >
            {{ isDeliveryReady ? 'Ready' : 'Needs Build' }}
          </Badge>
        </div>

        <CustomerPackageCard
          :package-asset="listingDraft.package_asset"
          :download-url="listingDraft.package_download_url"
          :version="listingDraft.version"
          :is-building="isBuildingPackage"
          @build-package="handleBuildPackage"
        />
      </section>

      <!-- ================================================== -->
      <!-- SUB-TAB 5: FINAL REVIEW & GATE 3                   -->
      <!-- ================================================== -->
      <section v-else-if="activeSubTab === 'final-review'" class="space-y-6" data-testid="subtab-final-review">
        <!-- Header -->
        <div class="p-4 sm:p-5 rounded-xl bg-card border border-border shadow-xs space-y-1">
          <h3 class="text-base font-bold text-foreground flex items-center gap-2">
            <Icon name="lucide:clipboard-check" class="size-5 text-primary" aria-hidden="true" />
            <span>Ready for Etsy?</span>
          </h3>
          <p class="text-xs text-muted-foreground">
            Review the final listing configuration before approving Gate 3.
          </p>
        </div>

        <!-- 4 Grouped Summaries Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Summary Card 1: Listing Content -->
          <Card class="border-border bg-card shadow-xs">
            <CardHeader class="p-4 pb-2 flex flex-row items-center justify-between gap-2">
              <CardTitle class="text-xs font-semibold flex items-center gap-2 text-foreground">
                <Icon name="lucide:file-text" class="size-4 text-primary" aria-hidden="true" />
                <span>Listing Content</span>
              </CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-xs text-primary hover:underline cursor-pointer"
                @click="setActiveSubTab('content')"
              >
                Edit Listing Content
              </Button>
            </CardHeader>
            <CardContent class="p-4 pt-1 space-y-2 text-xs">
              <div class="space-y-0.5">
                <span class="text-[11px] text-muted-foreground font-medium">Title</span>
                <p class="font-semibold text-foreground line-clamp-2">{{ localTitle || 'No title configured' }}</p>
              </div>
              <div class="flex items-center justify-between pt-1 border-t border-border/50 text-muted-foreground">
                <span>Description: <strong class="text-foreground font-medium">{{ localDescription ? 'Ready' : 'Missing' }}</strong></span>
                <span>Tags: <strong class="text-foreground font-medium">{{ localTags.length }} / 13</strong></span>
              </div>
            </CardContent>
          </Card>

          <!-- Summary Card 2: Etsy Details -->
          <Card class="border-border bg-card shadow-xs">
            <CardHeader class="p-4 pb-2 flex flex-row items-center justify-between gap-2">
              <CardTitle class="text-xs font-semibold flex items-center gap-2 text-foreground">
                <Icon name="lucide:store" class="size-4 text-primary" aria-hidden="true" />
                <span>Etsy Details</span>
              </CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-xs text-primary hover:underline cursor-pointer"
                @click="setActiveSubTab('etsy-details')"
              >
                Edit Etsy Details
              </Button>
            </CardHeader>
            <CardContent class="p-4 pt-1 space-y-1.5 text-xs">
              <div class="flex items-center justify-between">
                <span class="text-muted-foreground">Category:</span>
                <span class="font-semibold text-foreground truncate max-w-[200px]">Clip Art &amp; Image Files</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-muted-foreground">Price &amp; Quantity:</span>
                <span class="font-semibold text-foreground">{{ formattedPriceDisplay }} (Stock: {{ localQuantity }})</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-muted-foreground">SKU:</span>
                <span class="font-mono text-[11px] text-foreground truncate max-w-[180px]">{{ localSku || 'Not set' }}</span>
              </div>
              <div class="flex items-center justify-between pt-1 border-t border-border/50">
                <span class="text-muted-foreground">Renewal:</span>
                <span class="text-foreground font-medium">{{ localShouldAutoRenew ? 'Automatic' : 'Manual' }}</span>
              </div>
            </CardContent>
          </Card>

          <!-- Summary Card 3: IP & Compliance -->
          <Card class="border-border bg-card shadow-xs">
            <CardHeader class="p-4 pb-2 flex flex-row items-center justify-between gap-2">
              <CardTitle class="text-xs font-semibold flex items-center gap-2 text-foreground">
                <Icon name="lucide:shield-check" class="size-4 text-primary" aria-hidden="true" />
                <span>IP &amp; Compliance</span>
              </CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-xs text-primary hover:underline cursor-pointer"
                @click="setActiveSubTab('ip-compliance')"
              >
                Review IP
              </Button>
            </CardHeader>
            <CardContent class="p-4 pt-1 space-y-2 text-xs">
              <div class="flex items-center justify-between">
                <span class="text-muted-foreground">Screening Result:</span>
                <Badge
                  variant="outline"
                  class="text-[10px] font-mono font-semibold"
                  :class="isHighRisk ? 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20' : isWarning ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'"
                >
                  {{ riskLevel.toUpperCase() }} RISK
                </Badge>
              </div>
              <p class="text-[11px] text-muted-foreground leading-normal">
                {{ isHighRisk ? 'Approval blocked due to direct trademark conflict.' : isWarning ? 'Warning: Owner acknowledgement required.' : 'No material conflicts identified in current automated screening.' }}
              </p>
            </CardContent>
          </Card>

          <!-- Summary Card 4: Buyer Delivery -->
          <Card class="border-border bg-card shadow-xs">
            <CardHeader class="p-4 pb-2 flex flex-row items-center justify-between gap-2">
              <CardTitle class="text-xs font-semibold flex items-center gap-2 text-foreground">
                <Icon name="lucide:package-check" class="size-4 text-primary" aria-hidden="true" />
                <span>Buyer Delivery</span>
              </CardTitle>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-xs text-primary hover:underline cursor-pointer"
                @click="setActiveSubTab('delivery')"
              >
                Review Delivery
              </Button>
            </CardHeader>
            <CardContent class="p-4 pt-1 space-y-2 text-xs">
              <div class="flex items-center justify-between">
                <span class="text-muted-foreground">Deliverables:</span>
                <span class="font-semibold text-emerald-600 dark:text-emerald-400">4 / 4 files configured</span>
              </div>
              <p class="text-[11px] text-muted-foreground">
                Master PNG (4500x5400 px), Vector PDF, Commercial License, Print Guide
              </p>
            </CardContent>
          </Card>
        </div>

        <!-- Centralized Gate Readiness Checklist -->
        <Card class="border-border bg-card shadow-xs">
          <CardHeader class="p-4 sm:p-5 pb-3 flex flex-row items-center justify-between gap-3">
            <div class="space-y-0.5">
              <CardTitle class="text-sm font-semibold flex items-center gap-2">
                <Icon name="lucide:list-checks" class="size-4 text-primary" aria-hidden="true" />
                <span>Gate 3 Readiness Checklist</span>
              </CardTitle>
            </div>
            <Badge
              variant="outline"
              class="text-xs font-mono font-semibold"
              :class="canApprove ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'"
            >
              {{ canApprove ? 'Ready for Approval' : `${blockers.length} issues need attention` }}
            </Badge>
          </CardHeader>

          <CardContent class="p-4 sm:p-5 pt-0 space-y-2">
            <div
              v-for="check in readinessChecks"
              :key="check.id"
              class="flex items-center justify-between p-2.5 rounded-lg border text-xs transition-colors bg-muted/30 border-border text-foreground"
            >
              <div class="flex items-center gap-2.5 min-w-0">
                <Icon
                  :name="check.passed ? 'lucide:check-circle-2' : 'lucide:circle-alert'"
                  class="size-4 shrink-0"
                  :class="check.passed ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'"
                  aria-hidden="true"
                />
                <span class="font-medium truncate">{{ check.label }}</span>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <Button
                  v-if="!check.passed"
                  type="button"
                  variant="outline"
                  size="sm"
                  class="h-6 px-2 text-[11px] font-medium text-primary hover:bg-primary/10 cursor-pointer"
                  @click="setActiveSubTab(check.tab)"
                >
                  Fix
                </Button>
                <Badge v-else variant="outline" class="text-[10px] text-emerald-600 dark:text-emerald-400 border-emerald-500/20 bg-emerald-500/10">
                  Passed
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Sticky Gate 3 Decision Bar (Only in Final Review) -->
        <div
          v-if="!isApproved"
          class="bg-card/95 backdrop-blur-md border border-border/80 rounded-xl p-3.5 sm:p-4 shadow-lg ring-1 ring-black/5 dark:ring-white/10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 sticky bottom-3 sm:bottom-4 z-10"
        >
          <div class="space-y-1 text-center sm:text-left min-w-0">
            <h3 class="text-sm font-semibold text-foreground flex items-center justify-center sm:justify-start gap-2">
              <Icon name="lucide:shield-check" class="size-4 text-primary shrink-0" aria-hidden="true" />
              <span>Gate 3: Listing &amp; IP Approval</span>
            </h3>
            <div v-if="canApprove" class="flex items-center justify-center sm:justify-start gap-1.5 text-xs text-muted-foreground">
              <Icon name="lucide:circle-check" class="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
              <span class="text-foreground font-medium">All checks passed.</span>
              <span>Ready to approve for Etsy draft creation.</span>
            </div>
            <div v-else class="flex items-center justify-center sm:justify-start gap-1.5 text-xs text-amber-600 dark:text-amber-400 font-medium">
              <Icon name="lucide:triangle-alert" class="size-3.5 shrink-0" aria-hidden="true" />
              <span>{{ blockers.length }} issue{{ blockers.length > 1 ? 's' : '' }} need attention: {{ blockers[0]?.blockerMsg }}</span>
            </div>
          </div>

          <div class="flex items-center gap-2 sm:gap-3 justify-stretch sm:justify-end shrink-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              :disabled="isDecidingGate"
              class="text-xs h-9 px-3.5 gap-1.5 cursor-pointer text-muted-foreground hover:text-destructive hover:bg-destructive/10 hover:border-destructive/30 flex-1 sm:flex-initial justify-center transition-colors"
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
              class="text-xs h-9 px-4 gap-1.5 opacity-80 cursor-not-allowed flex-1 sm:flex-initial justify-center shadow-xs"
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
              class="text-xs h-9 px-4 gap-1.5 bg-amber-600 hover:bg-amber-700 text-white cursor-pointer flex-1 sm:flex-initial justify-center shadow-xs"
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
              class="text-xs h-9 px-4 gap-1.5 font-medium cursor-pointer shadow-xs flex-1 sm:flex-initial justify-center"
              @click="handleApprove"
            >
              <Icon v-if="isDecidingGate" name="lucide:loader-circle" class="size-4 animate-spin" aria-hidden="true" />
              <Icon v-else-if="isApproved" name="lucide:badge-check" class="size-4" aria-hidden="true" />
              <Icon v-else name="lucide:check-circle-2" class="size-4" aria-hidden="true" />
              <span>{{ isApproved ? 'Approved' : 'Approve for Etsy Draft' }}</span>
            </Button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
