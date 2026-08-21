<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { EtsyDraftVerification, EtsyVerificationCheck } from '~/types/etsy';
import { useEtsy } from '~/composables/useEtsy';
import Badge from '~/components/ui/Badge.vue';

const props = defineProps<{
  workflowId: string;
  listingId?: string | null;
  verification?: EtsyDraftVerification | null;
  shopManagerUrl?: string | null;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'recheck-completed', report: EtsyDraftVerification): void;
}>();

const { verifyEtsyDraft, updateEtsyDraft } = useEtsy();
const isRechecking = ref(false);
const isUpdatingDraft = ref(false);
const localVerification = ref<EtsyDraftVerification | null>(props.verification || null);
const expandedKeys = ref<Record<string, boolean>>({});

// Watch for prop updates
watch(
  () => props.verification,
  (newVal) => {
    if (newVal) {
      localVerification.value = newVal;
    }
  },
  { deep: true, immediate: true }
);

const summary = computed(() => {
  return localVerification.value?.summary || {
    synced: 0,
    warnings: 0,
    errors: 0,
    manual_review: 0,
    total: 0,
  };
});

const overallStatus = computed(() => {
  return localVerification.value?.status || 'needs_attention';
});

const statusBadgeVariant = computed(() => {
  switch (overallStatus.value) {
    case 'verified':
      return 'success';
    case 'failed':
      return 'destructive';
    case 'needs_attention':
    default:
      return 'warning';
  }
});

const formattedVerifiedAt = computed(() => {
  if (!localVerification.value?.verified_at) return null;
  try {
    const d = new Date(localVerification.value.verified_at);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return null;
  }
});

const checksByCategory = computed(() => {
  const checks = localVerification.value?.checks || [];
  return {
    listing: checks.filter((c) => c.category === 'listing'),
    commerce: checks.filter((c) => c.category === 'commerce'),
    media: checks.filter((c) => c.category === 'media_and_delivery'),
    attributes: checks.filter((c) => c.category === 'attributes'),
  };
});

const toggleExpand = (key: string) => {
  expandedKeys.value[key] = !expandedKeys.value[key];
};

const handleRecheck = async () => {
  if (isRechecking.value || isUpdatingDraft.value || props.disabled) return;
  isRechecking.value = true;
  try {
    const res = await verifyEtsyDraft(props.workflowId);
    if (res) {
      localVerification.value = res;
      emit('recheck-completed', res);
    }
  } catch (err) {
    console.error('Failed to re-verify Etsy draft:', err);
  } finally {
    isRechecking.value = false;
  }
};

const handleUpdateDraft = async () => {
  if (isUpdatingDraft.value || isRechecking.value || props.disabled) return;
  isUpdatingDraft.value = true;
  try {
    const res = await updateEtsyDraft(props.workflowId);
    if (res) {
      localVerification.value = res;
      emit('recheck-completed', res);
    }
  } catch (err) {
    console.error('Failed to update Etsy draft:', err);
  } finally {
    isUpdatingDraft.value = false;
  }
};

const copiedKey = ref<string | null>(null);

function copyToClipboard(text: string, key: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null;
    }, 2000);
  }
}

function getCheckBadgeText(check: EtsyVerificationCheck): string {
  if (check.key === 'shopping_cart_summary' && check.status === 'manual_review') {
    return 'Web Editor Only';
  }
  if (check.status === 'synced') {
    if (['title', 'description', 'item_metadata', 'category'].includes(check.key) || (check.actual && check.actual.length > 25)) {
      return 'Synced';
    }
    return check.actual || 'Synced';
  }
  if (check.status === 'different') {
    return 'Different';
  }
  if (check.status === 'missing') {
    return 'Missing';
  }
  if (check.status === 'failed') {
    return 'Failed';
  }
  if (check.status === 'manual_review') {
    return 'Manual in Etsy';
  }
  return check.actual || check.status;
}
</script>

<template>
  <div
    class="rounded-xl border border-border/80 bg-card p-5 shadow-sm transition-all"
    data-testid="etsy-verification-card"
  >
    <!-- Header -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/60 pb-4">
      <div class="flex items-center gap-3">
        <div
          class="flex size-9 shrink-0 items-center justify-center rounded-lg border"
          :class="[
            overallStatus === 'verified'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : overallStatus === 'needs_attention'
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'
                : 'border-rose-200 bg-rose-50 text-rose-700',
          ]"
        >
          <Icon
            :name="
              overallStatus === 'verified'
                ? 'lucide:shield-check'
                : overallStatus === 'needs_attention'
                  ? 'lucide:shield-alert'
                  : 'lucide:shield-x'
            "
            class="size-5"
            aria-hidden="true"
          />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-foreground">Post-Dispatch Etsy Draft Verification</h3>
            <Badge
              :variant="statusBadgeVariant"
              class="self-start sm:self-auto text-xs font-mono"
              data-testid="verification-status-badge"
            >
              <Icon
                :name="
                  overallStatus === 'verified'
                    ? 'lucide:check'
                    : overallStatus === 'needs_attention'
                      ? 'lucide:alert-triangle'
                      : 'lucide:x-circle'
                "
                class="size-3 mr-1"
                aria-hidden="true"
              />
              <span>
                {{
                  overallStatus === 'verified'
                    ? 'Verified'
                    : overallStatus === 'needs_attention'
                      ? `Needs Attention (${summary.warnings} items)`
                      : 'Verification Failed'
                }}
              </span>
            </Badge>
          </div>
          <p class="text-xs text-muted-foreground mt-0.5">
            Authoritative comparison of expected listing state vs live Etsy Open API v3 draft.
            <span v-if="formattedVerifiedAt" class="font-mono text-muted-foreground/80 ml-1">
              (Checked {{ formattedVerifiedAt }})
            </span>
          </p>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center gap-2 self-start sm:self-auto flex-wrap">
        <button
          type="button"
          :disabled="isUpdatingDraft || isRechecking || disabled"
          @click="handleUpdateDraft"
          class="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-xs cursor-pointer"
          data-testid="etsy-update-draft-btn"
        >
          <Icon
            v-if="isUpdatingDraft"
            name="lucide:loader-circle"
            class="size-3.5 animate-spin"
            aria-hidden="true"
          />
          <Icon
            v-else
            name="lucide:arrow-up-circle"
            class="size-3.5"
            aria-hidden="true"
          />
          <span>{{ isUpdatingDraft ? 'Updating Draft...' : 'Update Etsy Draft' }}</span>
        </button>

        <button
          type="button"
          :disabled="isRechecking || isUpdatingDraft || disabled"
          @click="handleRecheck"
          class="inline-flex items-center gap-1.5 rounded-lg border border-border/80 bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/60 transition-colors disabled:opacity-50 cursor-pointer"
          data-testid="etsy-recheck-btn"
        >
          <Icon
            name="lucide:refresh-cw"
            class="size-3.5 text-muted-foreground"
            :class="{ 'animate-spin': isRechecking }"
            aria-hidden="true"
          />
          <span>{{ isRechecking ? 'Checking Etsy...' : 'Re-check Etsy' }}</span>
        </button>
      </div>
    </div>

    <!-- Summary Stats Bar -->
    <div class="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
      <div class="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-2.5">
        <Icon name="lucide:circle-check" class="size-4 text-emerald-700 shrink-0" aria-hidden="true" />
        <div>
          <div class="font-semibold text-emerald-700 font-mono">{{ summary.synced }} Synced</div>
          <div class="text-[11px] text-muted-foreground">API Verified Match</div>
        </div>
      </div>

      <div class="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5">
        <Icon name="lucide:alert-triangle" class="size-4 text-amber-500 shrink-0" aria-hidden="true" />
        <div>
          <div class="font-semibold text-foreground font-mono">{{ summary.warnings }} Warnings</div>
          <div class="text-[11px] text-muted-foreground">Different or Missing</div>
        </div>
      </div>

      <div class="flex items-center gap-2 rounded-lg bg-muted/30 border border-border/50 p-2.5">
        <Icon name="lucide:list-checks" class="size-4 text-muted-foreground shrink-0" aria-hidden="true" />
        <div>
          <div class="font-semibold text-foreground">{{ (summary.synced || 0) + (summary.warnings || 0) + (summary.errors || 0) }} Total Checks</div>
          <div class="text-[11px] text-muted-foreground">100% Comprehensive API Checks</div>
        </div>
      </div>
    </div>

    <!-- Categorized Check Tables -->
    <div class="mt-5 space-y-4">
      <!-- 1. Listing Meta -->
      <div v-if="checksByCategory.listing.length > 0" class="rounded-lg border border-border/60 overflow-hidden">
        <div class="bg-muted/40 px-3 py-2 text-xs font-semibold text-foreground flex items-center gap-2">
          <Icon name="lucide:file-text" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Listing Content & Taxonomy</span>
        </div>
        <div class="divide-y divide-border/40 text-xs">
          <div
            v-for="check in checksByCategory.listing"
            :key="check.key"
            class="p-3 hover:bg-muted/20 transition-colors"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-start gap-2 min-w-0">
                <Icon
                  :name="
                    check.status === 'synced'
                      ? 'lucide:circle-check'
                      : check.status === 'manual_review'
                        ? 'lucide:info'
                        : check.status === 'different' || check.status === 'missing'
                          ? 'lucide:alert-triangle'
                          : check.status === 'failed'
                            ? 'lucide:x-circle'
                            : 'lucide:circle-dot'
                  "
                  class="size-4 shrink-0 mt-0.5"
                  :class="[
                    check.status === 'synced'
                      ? 'text-emerald-700'
                      : check.status === 'manual_review'
                        ? 'text-primary'
                        : check.status === 'different' || check.status === 'missing'
                          ? 'text-amber-600 dark:text-amber-400'
                          : check.status === 'failed'
                            ? 'text-rose-600 dark:text-rose-400'
                            : 'text-muted-foreground',
                  ]"
                  aria-hidden="true"
                />
                <div class="min-w-0">
                  <span class="font-medium text-foreground">{{ check.label }}</span>
                  <p
                    v-if="check.message"
                    class="text-[11px] mt-0.5"
                    :class="
                      check.status === 'synced' || check.status === 'manual_review'
                        ? 'text-muted-foreground truncate max-w-[260px] sm:max-w-[420px] font-normal'
                        : 'text-amber-600 dark:text-amber-400'
                    "
                  >
                    {{ check.message }}
                  </p>
                  <p v-else-if="check.key === 'title' && check.expected" class="text-[11px] text-muted-foreground truncate max-w-[260px] sm:max-w-[420px] mt-0.5 font-normal">
                    {{ check.expected }}
                  </p>
                </div>
              </div>

              <!-- Status Badge / Val -->
              <div class="flex items-center gap-2 shrink-0">
                <button
                  v-if="check.key === 'shopping_cart_summary' && check.details?.shopping_cart_summary"
                  type="button"
                  @click="copyToClipboard(check.details.shopping_cart_summary, 'cart-summary')"
                  class="inline-flex items-center gap-1 text-[11px] text-primary hover:underline px-1.5 py-0.5 rounded hover:bg-primary/10 transition-colors cursor-pointer"
                  title="Copy shopping cart summary to clipboard"
                >
                  <Icon :name="copiedKey === 'cart-summary' ? 'lucide:check' : 'lucide:copy'" class="size-3" aria-hidden="true" />
                  <span>{{ copiedKey === 'cart-summary' ? 'Copied' : 'Copy' }}</span>
                </button>

                <Badge
                  :variant="check.status === 'synced' ? 'success' : check.status === 'manual_review' ? 'secondary' : check.status === 'different' ? 'warning' : 'secondary'"
                  class="font-mono text-[11px]"
                >
                  {{ getCheckBadgeText(check) }}
                </Badge>
                <button
                  v-if="check.details || check.status === 'different' || check.key === 'title' || check.key === 'description'"
                  type="button"
                  @click="toggleExpand(check.key)"
                  class="text-[11px] text-primary hover:underline cursor-pointer"
                >
                  {{ expandedKeys[check.key] ? 'Hide' : 'Details' }}
                </button>
              </div>
            </div>

            <!-- Expandable Diff Panel -->
            <div
              v-if="expandedKeys[check.key]"
              class="mt-2.5 rounded bg-muted/40 p-2.5 text-[11px] space-y-1.5 border border-border/50 font-mono"
            >
              <div v-if="check.key === 'shopping_cart_summary'" class="space-y-1 text-muted-foreground">
                <div class="text-foreground font-semibold">Optional Etsy Web Editor Field:</div>
                <div class="text-[11px] font-sans text-foreground/90 leading-relaxed">
                  Etsy's Developer API does not provide a field for Shopping Cart Summary. You can click <b>Copy</b> above and paste it into Etsy's listing editor if you wish.
                </div>
              </div>
              <div v-else class="flex gap-2">
                <span class="text-muted-foreground shrink-0 w-16">Expected:</span>
                <span class="text-foreground break-all">{{ check.expected }}</span>
              </div>
              <div v-if="check.actual && check.key !== 'shopping_cart_summary'" class="flex gap-2">
                <span class="text-muted-foreground shrink-0 w-16">Actual:</span>
                <span class="text-foreground break-all">{{ check.actual }}</span>
              </div>
              <div v-if="check.details?.missing" class="text-amber-600 dark:text-amber-400">
                Missing on Etsy: {{ check.details.missing.join(', ') }}
              </div>
              <div v-if="check.details?.unexpected" class="text-muted-foreground">
                Unexpected on Etsy: {{ check.details.unexpected.join(', ') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Commerce -->
      <div v-if="checksByCategory.commerce.length > 0" class="rounded-lg border border-border/60 overflow-hidden">
        <div class="bg-muted/40 px-3 py-2 text-xs font-semibold text-foreground flex items-center gap-2">
          <Icon name="lucide:shopping-bag" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Pricing, Inventory & Organization</span>
        </div>
        <div class="divide-y divide-border/40 text-xs">
          <div
            v-for="check in checksByCategory.commerce"
            :key="check.key"
            class="p-3 hover:bg-muted/20 transition-colors"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-start gap-2 min-w-0">
                <Icon
                  :name="check.status === 'synced' ? 'lucide:circle-check' : 'lucide:alert-triangle'"
                  class="size-4 shrink-0 mt-0.5"
                  :class="check.status === 'synced' ? 'text-emerald-700' : 'text-amber-600'"
                  aria-hidden="true"
                />
                <div class="min-w-0">
                  <span class="font-medium text-foreground">{{ check.label }}</span>
                  <p
                    v-if="check.message"
                    class="text-[11px] mt-0.5"
                    :class="
                      check.status === 'synced'
                        ? 'text-muted-foreground truncate max-w-[260px] sm:max-w-[420px] font-normal'
                        : 'text-amber-600 dark:text-amber-400'
                    "
                  >
                    {{ check.message }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <Badge
                  :variant="check.status === 'synced' ? 'success' : 'warning'"
                  class="font-mono text-[11px]"
                >
                  {{ getCheckBadgeText(check) }}
                </Badge>
                <button
                  v-if="check.status !== 'synced' || check.details"
                  type="button"
                  @click="toggleExpand(check.key)"
                  class="text-[11px] text-primary hover:underline"
                >
                  {{ expandedKeys[check.key] ? 'Hide' : 'Inspect' }}
                </button>
              </div>
            </div>

            <div
              v-if="expandedKeys[check.key]"
              class="mt-2.5 rounded bg-muted/40 p-2.5 text-[11px] space-y-1 border border-border/50 font-mono"
            >
              <div><span class="text-muted-foreground">Expected:</span> {{ check.expected }}</div>
              <div><span class="text-muted-foreground">Actual:</span> {{ check.actual }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Media & Delivery -->
      <div v-if="checksByCategory.media.length > 0" class="rounded-lg border border-border/60 overflow-hidden">
        <div class="bg-muted/40 px-3 py-2 text-xs font-semibold text-foreground flex items-center gap-2">
          <Icon name="lucide:layers" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Mockup Images & Real Digital Download Deliverables</span>
        </div>
        <div class="divide-y divide-border/40 text-xs">
          <div
            v-for="check in checksByCategory.media"
            :key="check.key"
            class="p-3 hover:bg-muted/20 transition-colors"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-start gap-2 min-w-0">
                <Icon
                  :name="check.status === 'synced' ? 'lucide:circle-check' : 'lucide:alert-triangle'"
                  class="size-4 shrink-0 mt-0.5"
                  :class="check.status === 'synced' ? 'text-emerald-700' : 'text-amber-600'"
                  aria-hidden="true"
                />
                <div class="min-w-0">
                  <span class="font-medium text-foreground">{{ check.label }}</span>
                  <p
                    v-if="check.message"
                    class="text-[11px] mt-0.5"
                    :class="
                      check.status === 'synced'
                        ? 'text-muted-foreground truncate max-w-[260px] sm:max-w-[420px] font-normal'
                        : 'text-amber-600 dark:text-amber-400'
                    "
                  >
                    {{ check.message }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <Badge
                  variant="success"
                  class="font-mono text-[11px]"
                >
                  {{ getCheckBadgeText(check) }}
                </Badge>
                <button
                  v-if="check.details"
                  type="button"
                  @click="toggleExpand(check.key)"
                  class="text-[11px] text-primary hover:underline"
                >
                  {{ expandedKeys[check.key] ? 'Hide' : check.key === 'digital_files' ? 'Files' : 'Inspect' }}
                </button>
              </div>
            </div>

            <!-- Expandable Mockup Images Panel -->
            <div
              v-if="expandedKeys[check.key] && check.key === 'mockups'"
              class="mt-2.5 rounded bg-muted/40 p-2.5 text-[11px] space-y-2 border border-border/50 font-mono"
            >
              <div class="flex items-center justify-between text-muted-foreground">
                <span class="font-semibold">Live Etsy Preview Images:</span>
                <span>{{ check.details?.images?.length ? `${check.details.images.length} verified` : check.actual }}</span>
              </div>
              <div v-if="check.details?.images?.length" class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div
                  v-for="img in check.details.images"
                  :key="img.image_id || img.rank"
                  class="flex items-center gap-2 p-1.5 rounded bg-background/60 border border-border/40"
                >
                  <img
                    v-if="img.url"
                    :src="img.url"
                    alt="Mockup preview"
                    class="size-8 rounded object-cover border border-border/50 shrink-0"
                  />
                  <div v-else class="size-8 rounded bg-muted flex items-center justify-center shrink-0">
                    <Icon name="lucide:image" class="size-4 text-muted-foreground" aria-hidden="true" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="font-semibold text-foreground truncate">Rank #{{ img.rank }}</div>
                    <div class="text-[10px] text-muted-foreground truncate font-mono">ID: {{ img.image_id }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="text-muted-foreground">
                {{ check.actual }}
              </div>
            </div>

            <!-- Expandable Digital Files Panel -->
            <div
              v-if="expandedKeys[check.key] && check.key === 'digital_files'"
              class="mt-2.5 rounded bg-muted/40 p-2.5 text-[11px] space-y-1 border border-border/50 font-mono"
            >
              <div class="font-semibold text-muted-foreground mb-1">Attached Customer Files:</div>
              <div
                v-for="fn in check.details?.actual_filenames || []"
                :key="fn"
                class="flex items-center gap-1.5 text-foreground"
              >
                <Icon name="lucide:file-archive" class="size-3.5 text-primary" aria-hidden="true" />
                <span>{{ fn }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. Attributes -->
      <div v-if="checksByCategory.attributes.length > 0" class="rounded-lg border border-border/60 overflow-hidden">
        <div class="bg-muted/40 px-3 py-2 text-xs font-semibold text-foreground flex items-center gap-2">
          <Icon name="lucide:tag" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Category Attributes & Properties</span>
        </div>
        <div class="divide-y divide-border/40 text-xs">
          <div
            v-for="check in checksByCategory.attributes"
            :key="check.key"
            class="p-3 hover:bg-muted/20 transition-colors"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-start gap-2 min-w-0">
                <Icon
                  :name="check.status === 'synced' ? 'lucide:circle-check' : 'lucide:alert-triangle'"
                  class="size-4 shrink-0 mt-0.5"
                  :class="check.status === 'synced' ? 'text-emerald-700' : 'text-amber-600'"
                  aria-hidden="true"
                />
                <div class="min-w-0">
                  <span class="font-medium text-foreground">{{ check.label }}</span>
                  <p
                    v-if="check.message"
                    class="text-[11px] mt-0.5"
                    :class="
                      check.status === 'synced'
                        ? 'text-muted-foreground truncate max-w-[260px] sm:max-w-[420px] font-normal'
                        : 'text-amber-600 dark:text-amber-400'
                    "
                  >
                    {{ check.message }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <Badge
                  :variant="check.status === 'synced' ? 'success' : 'warning'"
                  class="font-mono text-[11px]"
                >
                  {{ getCheckBadgeText(check) }}
                </Badge>
                <button
                  v-if="check.details"
                  type="button"
                  @click="toggleExpand(check.key)"
                  class="text-[11px] text-primary hover:underline"
                >
                  {{ expandedKeys[check.key] ? 'Hide' : 'Inspect' }}
                </button>
              </div>
            </div>

            <div
              v-if="expandedKeys[check.key] && check.details?.properties"
              class="mt-2.5 rounded bg-muted/40 p-2.5 text-[11px] space-y-2 border border-border/50 font-mono"
            >
              <div
                v-for="p in check.details.properties"
                :key="p.property_id"
                class="p-2 rounded bg-background/60 border border-border/40 space-y-1"
              >
                <div class="flex items-center justify-between gap-2 font-semibold">
                  <span>{{ p.property_name || `Property #${p.property_id}` }}:</span>
                  <Badge
                    :variant="p.status === 'synced' ? 'success' : 'warning'"
                    class="text-[10px] font-mono px-1.5 py-0.5"
                  >
                    {{ p.status === 'synced' ? 'Synced' : p.status === 'missing' ? 'Missing on Etsy' : 'Different' }}
                  </Badge>
                </div>
                <div class="text-[10px] text-muted-foreground flex flex-col gap-0.5">
                  <div>Expected: <span class="text-foreground">{{ p.expected?.join(', ') || 'None' }}</span></div>
                  <div>Live on Etsy: <span class="text-foreground">{{ p.actual?.join(', ') || 'None' }}</span></div>
                  <div v-if="p.missing?.length" class="text-red-500 font-medium">
                    Missing on Etsy: {{ p.missing.join(', ') }}
                  </div>
                  <div v-if="p.unexpected?.length" class="text-amber-500 font-medium">
                    Extra on Etsy: {{ p.unexpected.join(', ') }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
