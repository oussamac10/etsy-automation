<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useListing } from '~/composables/useListing';
import EtsyDraftCard from './EtsyDraftCard.vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Badge from '~/components/ui/Badge.vue';
import Button from '~/components/ui/Button.vue';
import Alert from '~/components/ui/Alert.vue';
import AlertTitle from '~/components/ui/AlertTitle.vue';
import AlertDescription from '~/components/ui/AlertDescription.vue';
import { formatCurrencyAmount } from '~/utils/tags';
import { sanitizeUrl } from '~/utils/sanitize';

const props = defineProps<{
  workflowId: string;
  workflowState: string;
}>();

const { listingDraft, isLoading, errorMessage, loadListing } = useListing();

onMounted(async () => {
  await loadListing(props.workflowId);
});
</script>

<template>
  <div class="space-y-6" data-testid="workflow-etsy-tab">
    <!-- Header Banner -->
    <div class="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white rounded-xl p-5 sm:p-6 shadow-md border border-slate-700/50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <Icon name="lucide:store" class="size-5 text-primary" aria-hidden="true" />
          <h2 class="text-base sm:text-lg font-bold tracking-tight">Step 5: Etsy Draft</h2>
          <Badge variant="success" class="text-[10px] font-mono font-medium">
            Listing Approved
          </Badge>
        </div>
        <p class="text-xs text-slate-300 max-w-2xl leading-normal">
          Your digital artwork, tags, pricing, and metadata are approved. Click below to create your official draft listing on Etsy.
        </p>
      </div>
    </div>

    <!-- Error Alert -->
    <Alert v-if="errorMessage" variant="destructive" dismissible @dismiss="errorMessage = null">
      <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
      <AlertTitle>Listing Error</AlertTitle>
      <AlertDescription>{{ errorMessage }}</AlertDescription>
    </Alert>

    <!-- Main Dispatch Card -->
    <EtsyDraftCard
      :workflow-id="workflowId"
      :workflow-state="workflowState"
      :listing="listingDraft || undefined"
      @draft-created="loadListing(workflowId)"
    />

    <!-- Approved Listing Snapshot Summary -->
    <div v-if="listingDraft" class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
      <!-- Card 1: Pricing & SKU -->
      <Card class="border-border bg-card shadow-xs">
        <CardHeader class="p-4 pb-2">
          <CardTitle class="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
            <Icon name="lucide:tag" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Approved Pricing & SKU</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="p-4 pt-0 space-y-2">
          <div class="flex items-baseline justify-between">
            <span class="text-lg font-bold text-foreground">
              {{ formatCurrencyAmount(listingDraft.price_minor_units ?? 499, listingDraft.currency || 'USD') }}
            </span>
            <Badge variant="outline" class="text-[10px] font-mono">
              Stock: {{ listingDraft.quantity ?? 999 }}
            </Badge>
          </div>
          <div class="text-xs text-muted-foreground font-mono truncate">
            SKU: {{ listingDraft.sku || 'Auto-generated' }}
          </div>
        </CardContent>
      </Card>

      <!-- Card 2: Shop Organization -->
      <Card class="border-border bg-card shadow-xs">
        <CardHeader class="p-4 pb-2">
          <CardTitle class="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
            <Icon name="lucide:layers" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Shop Organization</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="p-4 pt-0 space-y-2">
          <div class="text-sm font-semibold text-foreground truncate">
            {{ listingDraft.shop_section_name || 'No Section (General)' }}
          </div>
          <div class="text-xs text-muted-foreground flex items-center gap-1">
            <Icon name="lucide:repeat" class="size-3" aria-hidden="true" />
            <span>Renewal: {{ listingDraft.should_auto_renew ? 'Automatic' : 'Manual' }}</span>
          </div>
        </CardContent>
      </Card>

      <!-- Card 3: Download Package -->
      <Card class="border-border bg-card shadow-xs">
        <CardHeader class="p-4 pb-2">
          <CardTitle class="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
            <Icon name="lucide:package-check" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Customer Package ZIP</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="p-4 pt-0 space-y-2">
          <div class="text-xs font-medium text-foreground truncate">
            {{ listingDraft.package_asset ? 'Print-Ready Package Available' : 'Digital ZIP Attached' }}
          </div>
          <a
            v-if="listingDraft.package_download_url"
            :href="sanitizeUrl(listingDraft.package_download_url)"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"
          >
            <Icon name="lucide:download" class="size-3" aria-hidden="true" />
            <span>Download Customer ZIP</span>
          </a>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
