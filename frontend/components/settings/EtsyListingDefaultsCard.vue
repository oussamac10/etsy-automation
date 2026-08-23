<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Label from '~/components/ui/Label.vue';
import Alert from '~/components/ui/Alert.vue';
import Skeleton from '~/components/ui/Skeleton.vue';
import { getApiErrorMessage, getCsrfHeaders } from '~/utils/api';

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

const SUPPORTED_CURRENCIES = [
  { code: 'USD', symbol: '$', label: 'US Dollar (USD)' },
  { code: 'EUR', symbol: '€', label: 'Euro (EUR)' },
  { code: 'GBP', symbol: '£', label: 'British Pound (GBP)' },
  { code: 'CAD', symbol: 'CA$', label: 'Canadian Dollar (CAD)' },
  { code: 'AUD', symbol: 'AU$', label: 'Australian Dollar (AUD)' },
];

const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);

const defaultPriceDecimal = ref('4.99');
const defaultQuantity = ref(999);
const defaultAutoRenew = ref(false);
const defaultStrategy = ref('match_niche');
const defaultCurrency = ref('USD');

// Initial state for dirty detection
const initialPriceMinor = ref(499);
const initialQuantity = ref(999);
const initialAutoRenew = ref(false);
const initialStrategy = ref('match_niche');
const initialCurrency = ref('USD');

const currencySymbol = computed(() => {
  const match = SUPPORTED_CURRENCIES.find((c) => c.code === defaultCurrency.value);
  return match ? match.symbol : '$';
});

async function loadSettings() {
  isLoading.value = true;
  errorMessage.value = null;
  try {
    const data = await $fetch<{
      default_digital_price_minor: number;
      default_digital_quantity: number;
      default_auto_renew: boolean;
      default_shop_section_strategy: string;
      currency?: string;
    }>(`${apiBase}/api/v1/settings`, {
      credentials: 'include',
    });

    if (data) {
      initialPriceMinor.value = data.default_digital_price_minor ?? 499;
      initialQuantity.value = data.default_digital_quantity ?? 999;
      initialAutoRenew.value = data.default_auto_renew ?? false;
      initialStrategy.value = data.default_shop_section_strategy || 'match_niche';
      initialCurrency.value = data.currency || 'USD';

      defaultPriceDecimal.value = (initialPriceMinor.value / 100).toFixed(2);
      defaultQuantity.value = initialQuantity.value;
      defaultAutoRenew.value = initialAutoRenew.value;
      defaultStrategy.value = initialStrategy.value;
      defaultCurrency.value = initialCurrency.value;
    }
  } catch (err: unknown) {
    errorMessage.value = getApiErrorMessage(err, 'Failed to load Etsy listing defaults.');
  } finally {
    isLoading.value = false;
  }
}

async function saveDefaults() {
  isSaving.value = true;
  errorMessage.value = null;
  successMessage.value = null;

  const minor = Math.round(parseFloat(defaultPriceDecimal.value || '4.99') * 100);

  try {
    await $fetch(`${apiBase}/api/v1/settings`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...getCsrfHeaders(),
      },
      body: {
        currency: defaultCurrency.value,
        default_digital_price_minor: minor,
        default_digital_quantity: defaultQuantity.value,
        default_auto_renew: defaultAutoRenew.value,
        default_shop_section_strategy: defaultStrategy.value,
      },
      credentials: 'include',
    });

    initialPriceMinor.value = minor;
    initialQuantity.value = defaultQuantity.value;
    initialAutoRenew.value = defaultAutoRenew.value;
    initialStrategy.value = defaultStrategy.value;
    initialCurrency.value = defaultCurrency.value;

    successMessage.value = 'Etsy listing defaults saved successfully.';
    setTimeout(() => {
      successMessage.value = null;
    }, 4000);
  } catch (err: unknown) {
    errorMessage.value = getApiErrorMessage(err, 'Failed to save listing defaults.');
  } finally {
    isSaving.value = false;
  }
}

const isDirty = computed(() => {
  const currentMinor = Math.round(parseFloat(defaultPriceDecimal.value || '0') * 100);
  return (
    currentMinor !== initialPriceMinor.value ||
    defaultCurrency.value !== initialCurrency.value ||
    defaultQuantity.value !== initialQuantity.value ||
    defaultAutoRenew.value !== initialAutoRenew.value ||
    defaultStrategy.value !== initialStrategy.value
  );
});

onMounted(() => {
  loadSettings();
});
</script>

<template>
  <Card class="border-border bg-card shadow-xs" data-testid="etsy-listing-defaults-card">
    <CardHeader class="p-4 sm:p-5 pb-3">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
            <Icon name="lucide:settings-2" class="size-4" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <CardTitle class="text-sm font-semibold tracking-tight">Etsy Listing Defaults</CardTitle>
            <CardDescription class="text-xs text-muted-foreground truncate">
              Default pricing, quantity, and renewal preference for new listing drafts.
            </CardDescription>
          </div>
        </div>

        <Button
          v-if="isDirty"
          type="button"
          variant="default"
          size="sm"
          :disabled="isSaving"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer"
          @click="saveDefaults"
        >
          <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save Defaults</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <Alert
        v-if="errorMessage"
        variant="destructive"
        title="Error"
        :description="errorMessage"
        dismissible
        @dismiss="errorMessage = null"
      />

      <Alert
        v-if="successMessage"
        variant="success"
        title="Saved"
        :description="successMessage"
        dismissible
        @dismiss="successMessage = null"
      />

      <!-- Loading Skeletons -->
      <div v-if="isLoading" class="space-y-4 py-2" data-testid="defaults-card-loading">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <Skeleton class="h-3.5 w-28" />
              <Skeleton class="h-4 w-24 rounded" />
            </div>
            <Skeleton class="h-9 w-full rounded-md" />
            <Skeleton class="h-3 w-40" />
          </div>
          <div class="space-y-2">
            <Skeleton class="h-3.5 w-32" />
            <Skeleton class="h-9 w-full rounded-md" />
            <Skeleton class="h-3 w-48" />
          </div>
        </div>
        <div class="space-y-2 pt-2 border-t border-border/40">
          <Skeleton class="h-3.5 w-32" />
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <Skeleton class="h-16 rounded-lg" />
            <Skeleton class="h-16 rounded-lg" />
          </div>
        </div>
      </div>

      <div v-else class="space-y-4">
        <!-- Price & Quantity Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <Label for="default-price" class="text-xs font-semibold text-foreground">Default Digital Price</Label>
              <!-- Currency Selector -->
              <div class="flex items-center gap-1" data-testid="default-currency-selector">
                <button
                  v-for="curr in SUPPORTED_CURRENCIES"
                  :key="curr.code"
                  type="button"
                  class="px-1.5 py-0.5 text-[10px] rounded font-mono transition-colors cursor-pointer"
                  :class="
                    defaultCurrency === curr.code
                      ? 'bg-primary text-primary-foreground font-bold shadow-2xs'
                      : 'bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted'
                  "
                  @click="defaultCurrency = curr.code"
                >
                  {{ curr.code }}
                </button>
              </div>
            </div>
            <div class="relative flex items-center">
              <span class="absolute left-3 text-xs font-medium text-muted-foreground">{{ currencySymbol }}</span>
              <Input
                id="default-price"
                v-model="defaultPriceDecimal"
                type="number"
                step="0.01"
                min="0.20"
                max="1000"
                class="pl-7 h-9 text-xs font-mono"
              />
            </div>
            <p class="text-[11px] text-muted-foreground">Pre-populates new listing drafts in {{ defaultCurrency }}.</p>
          </div>

          <div class="space-y-1.5">
            <Label for="default-quantity" class="text-xs font-semibold text-foreground">Default Stock Quantity</Label>
            <Input
              id="default-quantity"
              v-model.number="defaultQuantity"
              type="number"
              min="1"
              max="9999"
              class="h-9 text-xs font-mono"
            />
            <p class="text-[11px] text-muted-foreground">Digital quantity for new listing drafts (default 999).</p>
          </div>
        </div>

        <!-- Renewal Mode Options -->
        <div class="space-y-1.5 pt-1 border-t border-border/40">
          <Label class="text-xs font-semibold text-foreground">
            Default Renewal Mode
          </Label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              type="button"
              class="flex flex-col text-left p-3 rounded-lg border text-xs transition-colors cursor-pointer"
              :class="!defaultAutoRenew ? 'border-primary bg-primary/5 text-foreground' : 'border-border bg-card text-muted-foreground hover:border-primary/40'"
              @click="defaultAutoRenew = false"
            >
              <span class="font-semibold text-xs flex items-center gap-1.5 text-foreground">
                <Icon name="lucide:pause-circle" class="size-3.5 text-primary" aria-hidden="true" />
                Manual (Default)
              </span>
              <span class="text-[11px] text-muted-foreground mt-0.5 leading-normal">Expires after 4 months unless manually renewed.</span>
            </button>

            <button
              type="button"
              class="flex flex-col text-left p-3 rounded-lg border text-xs transition-colors cursor-pointer"
              :class="defaultAutoRenew ? 'border-primary bg-primary/5 text-foreground' : 'border-border bg-card text-muted-foreground hover:border-primary/40'"
              @click="defaultAutoRenew = true"
            >
              <span class="font-semibold text-xs flex items-center gap-1.5 text-foreground">
                <Icon name="lucide:repeat" class="size-3.5 text-primary" aria-hidden="true" />
                Automatic Renewal
              </span>
              <span class="text-[11px] text-muted-foreground mt-0.5 leading-normal">Renews automatically every 4 months ($0.20 per cycle).</span>
            </button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
