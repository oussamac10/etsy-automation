<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { PriceRecommendation } from '~/types/listing';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Label from '~/components/ui/Label.vue';

const props = defineProps<{
  workflowId: string;
  priceMinorUnits?: number | null;
  currency?: string | null;
  quantity?: number | null;
  sku?: string | null;
  isSaving?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:priceMinorUnits', val: number): void;
  (e: 'update:currency', val: string): void;
  (e: 'update:quantity', val: number): void;
  (e: 'update:sku', val: string): void;
  (e: 'save'): void;
}>();

const localCurrency = ref(props.currency || 'USD');
const localQuantity = ref(props.quantity || 999);
const localSku = ref(props.sku || '');

// Price formatted as decimal string (e.g. 4.99)
const localPriceDecimal = ref(
  props.priceMinorUnits !== undefined && props.priceMinorUnits !== null
    ? (props.priceMinorUnits / 100).toFixed(2)
    : '4.99'
);

watch(
  () => props.priceMinorUnits,
  (newVal) => {
    if (newVal !== undefined && newVal !== null) {
      localPriceDecimal.value = (newVal / 100).toFixed(2);
    }
  }
);

watch(
  () => props.currency,
  (newVal) => {
    if (newVal) localCurrency.value = newVal;
  }
);

watch(
  () => props.quantity,
  (newVal) => {
    if (newVal !== undefined && newVal !== null) localQuantity.value = newVal;
  }
);

watch(
  () => props.sku,
  (newVal) => {
    if (newVal !== undefined && newVal !== null) localSku.value = newVal;
  }
);

const currencySymbol = computed(() => {
  const c = localCurrency.value.toUpperCase();
  if (c === 'EUR') return '€';
  if (c === 'GBP') return '£';
  if (c === 'CAD' || c === 'AUD') return '$';
  return '$';
});

// Price recommendation loading
const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';
const recommendation = ref<PriceRecommendation | null>(null);
const isLoadingRec = ref(false);

async function loadRecommendation() {
  if (!props.workflowId) return;
  isLoadingRec.value = true;
  try {
    const data = await $fetch<PriceRecommendation>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/price-recommendation`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    if (data && typeof data === 'object' && typeof data.recommended_minor_units === 'number') {
      recommendation.value = data;
    } else {
      recommendation.value = null;
    }
  } catch {
    recommendation.value = null;
  } finally {
    isLoadingRec.value = false;
  }
}

onMounted(() => {
  loadRecommendation();
});

function applyRecommendation() {
  if (!recommendation.value) return;
  const minor = recommendation.value.recommended_minor_units;
  localPriceDecimal.value = (minor / 100).toFixed(2);
  localCurrency.value = recommendation.value.currency;
  emit('update:priceMinorUnits', minor);
  emit('update:currency', recommendation.value.currency);
}

function onPriceChange() {
  const parsed = parseFloat(localPriceDecimal.value);
  if (!isNaN(parsed) && parsed > 0) {
    const minor = Math.round(parsed * 100);
    emit('update:priceMinorUnits', minor);
  }
}

function onQuantityChange() {
  const parsed = parseInt(String(localQuantity.value), 10);
  if (!isNaN(parsed) && parsed > 0) {
    emit('update:quantity', parsed);
  }
}

function onSkuChange() {
  emit('update:sku', localSku.value.trim());
}

const isDirty = computed(() => {
  const currentMinor = Math.round(parseFloat(localPriceDecimal.value || '0') * 100);
  return (
    currentMinor !== (props.priceMinorUnits || 499) ||
    localCurrency.value !== (props.currency || 'USD') ||
    localQuantity.value !== (props.quantity || 999) ||
    localSku.value !== (props.sku || '')
  );
});
</script>

<template>
  <div class="rounded-xl border border-border bg-card text-card-foreground shadow-xs p-5 space-y-5" data-testid="pricing-inventory-card">
    <div class="flex items-center justify-between border-b border-border/60 pb-3">
      <div class="flex items-center gap-2.5">
        <div class="flex size-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200">
          <Icon name="lucide:tag" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-foreground">Pricing &amp; Inventory</h3>
          <p class="text-2xs text-muted-foreground">Digital listing price, quantity, and internal SKU</p>
        </div>
      </div>

      <Button
        v-if="isDirty"
        type="button"
        size="sm"
        variant="default"
        :disabled="isSaving"
        class="text-xs h-7 px-2.5 gap-1.5 cursor-pointer"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:check" class="size-3" aria-hidden="true" />
        <span>Save</span>
      </Button>
    </div>

    <!-- Pricing Row -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
      <!-- Listing Price Input -->
      <div class="space-y-1.5">
        <Label for="listing-price" class="text-xs font-medium flex items-center justify-between">
          <span>Digital Listing Price</span>
          <span class="text-2xs font-normal text-muted-foreground">{{ localCurrency }}</span>
        </Label>
        <div class="relative flex items-center">
          <span class="absolute left-3 text-sm font-medium text-muted-foreground">{{ currencySymbol }}</span>
          <Input
            id="listing-price"
            v-model="localPriceDecimal"
            type="number"
            step="0.01"
            min="0.20"
            max="1000"
            placeholder="4.99"
            class="pl-7 pr-3 h-9 text-sm font-mono"
            @change="onPriceChange"
            @blur="onPriceChange"
          />
        </div>
      </div>

      <!-- Quantity Input -->
      <div class="space-y-1.5">
        <Label for="listing-quantity" class="text-xs font-medium flex items-center justify-between">
          <span>Digital Stock Quantity</span>
          <span class="text-2xs text-muted-foreground font-normal">Auto-replenishes</span>
        </Label>
        <div class="relative flex items-center">
          <Input
            id="listing-quantity"
            v-model.number="localQuantity"
            type="number"
            step="1"
            min="1"
            max="9999"
            placeholder="999"
            class="h-9 text-sm font-mono"
            @change="onQuantityChange"
            @blur="onQuantityChange"
          />
        </div>
      </div>
    </div>

    <!-- Pricing Recommendation Box -->
    <div v-if="recommendation" class="bg-emerald-50/50 border border-emerald-200/80 rounded-lg p-3 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 text-emerald-800 text-xs font-semibold">
          <Icon name="lucide:sparkles" class="size-3.5 text-emerald-600" aria-hidden="true" />
          <span>Recommended: {{ recommendation.formatted_price }}</span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          class="h-6 px-2 text-2xs bg-white text-emerald-700 border-emerald-300 hover:bg-emerald-100/50 cursor-pointer"
          @click="applyRecommendation"
        >
          Use recommended
        </Button>
      </div>
      <p class="text-2xs text-emerald-700 leading-relaxed">{{ recommendation.rationale }}</p>
      <div v-if="recommendation?.factors && recommendation.factors.length" class="flex flex-wrap gap-1 pt-1">
        <span
          v-for="factor in recommendation.factors"
          :key="factor"
          class="inline-flex items-center text-2xs bg-emerald-100/60 text-emerald-800 px-1.5 py-0.5 rounded border border-emerald-200"
        >
          {{ factor }}
        </span>
      </div>
    </div>

    <!-- Internal SKU Row -->
    <div class="space-y-1.5 pt-1">
      <Label for="listing-sku" class="text-xs font-medium flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <Icon name="lucide:barcode" class="size-3.5 text-muted-foreground" aria-hidden="true" />
          <span>Internal SKU</span>
        </div>
        <span class="text-2xs text-muted-foreground font-normal">Deterministic &amp; Unique</span>
      </Label>
      <Input
        id="listing-sku"
        v-model="localSku"
        type="text"
        placeholder="NCP-RETRO-CHRISTMAS-A1B2"
        maxlength="64"
        class="h-9 text-xs font-mono"
        @change="onSkuChange"
        @blur="onSkuChange"
      />
      <p class="text-2xs text-muted-foreground">
        Generated from shop name, design niche keywords, and stable hash. Used for stock management and Etsy inventory tracking.
      </p>
    </div>
  </div>
</template>
