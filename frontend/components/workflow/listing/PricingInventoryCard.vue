<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { PriceRecommendation } from '~/types/listing';
import { generateFrontendSku } from '~/utils/sku';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Label from '~/components/ui/Label.vue';
import Badge from '~/components/ui/Badge.vue';

const props = defineProps<{
  workflowId: string;
  title?: string | null;
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
  { code: 'USD', symbol: '$' },
  { code: 'EUR', symbol: '€' },
  { code: 'GBP', symbol: '£' },
  { code: 'CAD', symbol: 'CA$' },
  { code: 'AUD', symbol: 'AU$' },
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
    if (newVal !== undefined && newVal !== null) {
      localSku.value = newVal;
    }
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
  if (!localSku.value) {
    localSku.value = generateFrontendSku(props.title, props.workflowId);
    emit('update:sku', localSku.value);
  }
});

function handleGenerateSku() {
  localSku.value = generateFrontendSku(props.title, props.workflowId);
  emit('update:sku', localSku.value);
}

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
  <Card class="border-border bg-card shadow-xs" data-testid="pricing-inventory-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:tag" class="size-4 text-primary" aria-hidden="true" />
          <span>Pricing &amp; Inventory</span>
        </CardTitle>
        <CardDescription class="text-xs">
          Digital listing price, quantity, currency, and internal SKU.
        </CardDescription>
      </div>

      <Button
        v-if="isDirty"
        type="button"
        variant="default"
        size="sm"
        :disabled="isSaving"
        class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer self-start sm:self-auto"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
        <span>Save</span>
      </Button>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Price & Quantity Inputs -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
        <!-- Price Input -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <Label for="listing-price" class="text-xs font-semibold text-foreground">
              Digital Listing Price
            </Label>
            <!-- Currency Selector -->
            <div class="flex items-center gap-1">
              <button
                v-for="curr in SUPPORTED_CURRENCIES"
                :key="curr.code"
                type="button"
                class="px-1.5 py-0.5 text-[10px] rounded font-mono transition-colors cursor-pointer"
                :class="
                  localCurrency === curr.code
                    ? 'bg-primary text-primary-foreground font-bold shadow-2xs'
                    : 'bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted'
                "
                @click="onCurrencySelect(curr.code)"
              >
                {{ curr.code }}
              </button>
            </div>
          </div>

          <div class="relative flex items-center">
            <span class="absolute left-3 text-sm font-semibold text-muted-foreground">
              {{ currencySymbol }}
            </span>
            <Input
              id="listing-price"
              v-model="localPriceDecimal"
              type="number"
              step="0.01"
              min="0.20"
              max="50000.00"
              placeholder="4.99"
              class="pl-7 h-9 text-sm font-semibold font-mono"
              @change="onPriceChange"
              @blur="onPriceChange"
            />
          </div>
        </div>

        <!-- Quantity Input -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <Label for="listing-quantity" class="text-xs font-semibold text-foreground">
              Stock Quantity
            </Label>
            <span class="text-[11px] text-muted-foreground">Digital Instant</span>
          </div>

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

      <!-- Pricing Recommendation Callout -->
      <div v-if="recommendation" class="bg-muted/40 border border-border rounded-lg p-3 space-y-2">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            <Icon name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
            <span class="text-xs font-semibold text-foreground">
              Smart Recommended Price: {{ recommendation.formatted_price }}
            </span>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            class="h-7 px-2 text-xs font-medium shrink-0 cursor-pointer"
            @click="applyRecommendation"
          >
            <Icon name="lucide:check" class="size-3 text-primary" aria-hidden="true" />
            <span>Use recommendation</span>
          </Button>
        </div>

        <p class="text-xs text-muted-foreground leading-normal">
          {{ recommendation.rationale }}
        </p>

        <div v-if="recommendation?.factors && recommendation.factors.length" class="flex flex-wrap gap-1">
          <Badge
            v-for="factor in recommendation.factors"
            :key="factor"
            variant="outline"
            class="text-[10px] font-normal text-muted-foreground bg-background"
          >
            {{ factor }}
          </Badge>
        </div>
      </div>

      <!-- SKU Input -->
      <div class="space-y-1.5 pt-1 border-t border-border/40">
        <div class="flex items-center justify-between">
          <Label for="listing-sku" class="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <span>Internal SKU</span>
            <span class="text-[11px] text-muted-foreground font-normal" title="SKU is your internal product identifier. Buyers do not need it.">(Internal product ID)</span>
          </Label>

          <button
            type="button"
            class="text-[11px] text-primary hover:underline cursor-pointer font-medium flex items-center gap-1"
            title="Auto-generate a clean SKU"
            @click="handleGenerateSku"
          >
            <Icon name="lucide:sparkles" class="size-3" aria-hidden="true" />
            <span>Auto-generate</span>
          </button>
        </div>

        <div class="relative flex items-center">
          <Input
            id="listing-sku"
            v-model="localSku"
            type="text"
            placeholder="e.g. NCP-ART-A1B2"
            maxlength="64"
            class="h-9 pr-16 text-xs font-mono tracking-wide"
            @input="emit('update:sku', localSku)"
            @change="onSkuChange"
            @blur="onSkuChange"
          />
          <button
            type="button"
            class="absolute right-2 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors cursor-pointer flex items-center gap-1"
            title="Copy SKU to clipboard"
            @click="copySku"
          >
            <Icon :name="skuCopied ? 'lucide:check' : 'lucide:copy'" class="size-3" aria-hidden="true" />
            <span>{{ skuCopied ? 'Copied' : 'Copy' }}</span>
          </button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
