<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { PriceRecommendation } from '~/types/listing';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
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
const skuCopied = ref(false);

const SUPPORTED_CURRENCIES = [
  { code: 'USD', symbol: '$', name: 'USD ($)' },
  { code: 'EUR', symbol: '€', name: 'EUR (€)' },
  { code: 'GBP', symbol: '£', name: 'GBP (£)' },
  { code: 'CAD', symbol: 'CA$', name: 'CAD ($)' },
  { code: 'AUD', symbol: 'AU$', name: 'AUD ($)' },
];

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
  return '$';
});

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

function onCurrencySelect(c: string) {
  localCurrency.value = c;
  emit('update:currency', c);
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

async function copySku() {
  if (!localSku.value) return;
  try {
    await navigator.clipboard.writeText(localSku.value);
    skuCopied.value = true;
    setTimeout(() => {
      skuCopied.value = false;
    }, 2000);
  } catch {
    // ignore
  }
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
  <Card
    class="shadow-xs border border-border bg-card transition-all duration-200"
    data-testid="pricing-inventory-card"
  >
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 shadow-2xs">
            <Icon name="lucide:tag" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base font-semibold">Pricing &amp; Inventory</CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Digital listing price, currency, quantity, and internal SKU
            </CardDescription>
          </div>
        </div>

        <Button
          v-if="isDirty"
          type="button"
          size="sm"
          variant="default"
          :disabled="isSaving"
          class="text-xs h-8 px-3 gap-1.5 cursor-pointer shadow-2xs font-medium"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
          <span>Save Changes</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="pt-4 space-y-5">
      <!-- Pricing Row & Currency Selector -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
        <!-- Listing Price Input -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <Label for="listing-price" class="text-xs font-medium text-foreground">Digital Listing Price</Label>
            <!-- Currency selector pills -->
            <div class="flex items-center gap-1">
              <button
                v-for="curr in SUPPORTED_CURRENCIES"
                :key="curr.code"
                type="button"
                class="px-1.5 py-0.5 text-2xs rounded font-mono transition-all cursor-pointer"
                :class="localCurrency === curr.code ? 'bg-primary/10 text-primary font-bold border border-primary/30' : 'text-muted-foreground hover:bg-muted/60'"
                @click="onCurrencySelect(curr.code)"
              >
                {{ curr.code }}
              </button>
            </div>
          </div>

          <div class="relative flex items-center">
            <span class="absolute left-3 text-sm font-semibold text-muted-foreground">{{ currencySymbol }}</span>
            <Input
              id="listing-price"
              v-model="localPriceDecimal"
              type="number"
              step="0.01"
              min="0.20"
              max="1000"
              placeholder="4.99"
              class="pl-7 pr-3 h-9 text-sm font-mono font-medium focus:ring-1"
              @change="onPriceChange"
              @blur="onPriceChange"
            />
          </div>
        </div>

        <!-- Quantity Input -->
        <div class="space-y-1.5">
          <Label for="listing-quantity" class="text-xs font-medium flex items-center justify-between">
            <span>Digital Stock Quantity</span>
            <span class="text-2xs text-emerald-600 font-medium flex items-center gap-1">
              <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Auto-replenishes
            </span>
          </Label>
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

      <!-- Pricing Recommendation Box -->
      <div v-if="recommendation" class="bg-gradient-to-r from-emerald-500/5 via-teal-500/5 to-emerald-500/10 border border-emerald-500/20 rounded-xl p-3.5 space-y-2.5 shadow-2xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="flex size-6 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-700">
              <Icon name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
            </div>
            <span class="text-xs font-bold text-emerald-900 dark:text-emerald-300">
              AI Recommendation: {{ recommendation.formatted_price }}
            </span>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            class="h-7 px-2.5 text-2xs font-semibold bg-white dark:bg-card text-emerald-700 border-emerald-300 hover:bg-emerald-100/50 cursor-pointer shadow-2xs"
            @click="applyRecommendation"
          >
            <Icon name="lucide:check-check" class="size-3 text-emerald-600" aria-hidden="true" />
            <span>Use recommended</span>
          </Button>
        </div>

        <p class="text-2xs text-emerald-800/90 dark:text-emerald-300/90 leading-relaxed font-normal">
          {{ recommendation.rationale }}
        </p>

        <div v-if="recommendation?.factors && recommendation.factors.length" class="flex flex-wrap gap-1.5 pt-0.5">
          <span
            v-for="factor in recommendation.factors"
            :key="factor"
            class="inline-flex items-center gap-1 text-2xs bg-emerald-500/10 text-emerald-800 dark:text-emerald-200 px-2 py-0.5 rounded-md border border-emerald-500/20 font-medium"
          >
            <Icon name="lucide:check" class="size-2.5 text-emerald-600" aria-hidden="true" />
            {{ factor }}
          </span>
        </div>
      </div>

      <!-- Internal SKU Row -->
      <div class="space-y-1.5 pt-1 border-t border-border/40">
        <Label for="listing-sku" class="text-xs font-medium flex items-center justify-between">
          <div class="flex items-center gap-1.5">
            <Icon name="lucide:barcode" class="size-3.5 text-muted-foreground" aria-hidden="true" />
            <span>Deterministic Internal SKU</span>
          </div>
          <span class="text-2xs text-muted-foreground font-normal">Unique &amp; Stable across retries</span>
        </Label>
        <div class="relative flex items-center">
          <Input
            id="listing-sku"
            v-model="localSku"
            type="text"
            placeholder="NCP-RETRO-CHRISTMAS-A1B2"
            maxlength="64"
            class="h-9 pr-20 text-xs font-mono tracking-wide"
            @change="onSkuChange"
            @blur="onSkuChange"
          />
          <button
            type="button"
            class="absolute right-2 px-2 py-1 text-2xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded transition-colors cursor-pointer flex items-center gap-1"
            @click="copySku"
          >
            <Icon :name="skuCopied ? 'lucide:check' : 'lucide:copy'" class="size-3" aria-hidden="true" />
            <span>{{ skuCopied ? 'Copied' : 'Copy' }}</span>
          </button>
        </div>
        <p class="text-2xs text-muted-foreground">
          Derived from shop name prefix, key product terms, and workflow hash. Syncs to Etsy listing inventory.
        </p>
      </div>
    </CardContent>
  </Card>
</template>
