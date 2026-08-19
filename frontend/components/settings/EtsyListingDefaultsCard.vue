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
import AlertTitle from '~/components/ui/AlertTitle.vue';
import AlertDescription from '~/components/ui/AlertDescription.vue';
import { getApiErrorMessage, getCsrfHeaders } from '~/utils/api';

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);

const defaultPriceDecimal = ref('4.99');
const defaultQuantity = ref(999);
const defaultAutoRenew = ref(false);
const defaultStrategy = ref('match_niche');

// Initial state for dirty detection
const initialPriceMinor = ref(499);
const initialQuantity = ref(999);
const initialAutoRenew = ref(false);
const initialStrategy = ref('match_niche');

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

      defaultPriceDecimal.value = (initialPriceMinor.value / 100).toFixed(2);
      defaultQuantity.value = initialQuantity.value;
      defaultAutoRenew.value = initialAutoRenew.value;
      defaultStrategy.value = initialStrategy.value;
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
  <Card class="shadow-xs border border-border bg-card transition-all duration-200" data-testid="etsy-listing-defaults-card">
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 border border-amber-500/20 shadow-2xs">
            <Icon name="lucide:settings-2" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base font-semibold">Etsy Listing Defaults</CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Default pricing, stock quantity, renewal mode, and shop section rules for new listings
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
          @click="saveDefaults"
        >
          <Icon v-if="isSaving" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
          <span>Save Defaults</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="pt-4 space-y-4">
      <Alert v-if="errorMessage" variant="destructive" dismissible @dismiss="errorMessage = null">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{{ errorMessage }}</AlertDescription>
      </Alert>

      <Alert v-if="successMessage" variant="success" dismissible @dismiss="successMessage = null">
        <Icon name="lucide:circle-check" class="size-4" aria-hidden="true" />
        <AlertTitle>Saved</AlertTitle>
        <AlertDescription>{{ successMessage }}</AlertDescription>
      </Alert>

      <div v-if="isLoading" class="text-muted-foreground text-sm animate-pulse py-4 flex items-center gap-2">
        <Icon name="lucide:loader-circle" class="size-4 animate-spin text-primary" aria-hidden="true" />
        <span>Loading listing defaults...</span>
      </div>

      <div v-else class="space-y-4">
        <!-- Price & Quantity Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <Label for="default-price" class="text-xs font-medium text-foreground">Default Digital Price</Label>
            <div class="relative flex items-center">
              <span class="absolute left-3 text-xs font-semibold text-muted-foreground">$</span>
              <Input
                id="default-price"
                v-model="defaultPriceDecimal"
                type="number"
                step="0.01"
                min="0.20"
                max="1000"
                class="pl-7 h-9 text-xs font-mono font-medium"
              />
            </div>
            <p class="text-2xs text-muted-foreground">Pre-populates new listing drafts before manual adjustments.</p>
          </div>

          <div class="space-y-1.5">
            <Label for="default-quantity" class="text-xs font-medium text-foreground">Default Stock Quantity</Label>
            <Input
              id="default-quantity"
              v-model.number="defaultQuantity"
              type="number"
              min="1"
              max="9999"
              class="h-9 text-xs font-mono font-medium"
            />
            <p class="text-2xs text-muted-foreground">Digital stock quantity for new listing drafts (default 999).</p>
          </div>
        </div>

        <!-- Renewal Mode Options -->
        <div class="space-y-2 pt-2 border-t border-border/40">
          <Label class="text-xs font-medium text-foreground flex items-center gap-1.5">
            <Icon name="lucide:rotate-cw" class="size-3.5 text-amber-500" aria-hidden="true" />
            <span>Default Renewal Mode</span>
          </Label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="button"
              class="flex flex-col text-left p-3 rounded-xl border text-xs transition-all cursor-pointer shadow-2xs"
              :class="!defaultAutoRenew ? 'border-primary bg-primary/5 text-foreground ring-1 ring-primary/20' : 'border-border bg-muted/20 text-muted-foreground hover:bg-muted/40'"
              @click="defaultAutoRenew = false"
            >
              <span class="font-semibold text-xs flex items-center gap-1.5 text-foreground">
                <Icon name="lucide:pause-circle" class="size-3.5 text-muted-foreground" aria-hidden="true" />
                Manual Renewal (Default)
              </span>
              <span class="text-2xs text-muted-foreground mt-1 leading-tight">Listings expire after 4 months unless manually renewed.</span>
            </button>

            <button
              type="button"
              class="flex flex-col text-left p-3 rounded-xl border text-xs transition-all cursor-pointer shadow-2xs"
              :class="defaultAutoRenew ? 'border-primary bg-primary/5 text-foreground ring-1 ring-primary/20' : 'border-border bg-muted/20 text-muted-foreground hover:bg-muted/40'"
              @click="defaultAutoRenew = true"
            >
              <span class="font-semibold text-xs flex items-center gap-1.5 text-foreground">
                <Icon name="lucide:repeat" class="size-3.5 text-emerald-600" aria-hidden="true" />
                Automatic Renewal
              </span>
              <span class="text-2xs text-muted-foreground mt-1 leading-tight">Listings renew automatically upon expiration ($0.20 per cycle).</span>
            </button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
