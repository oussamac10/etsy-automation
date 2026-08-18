<script setup lang="ts">
import { ref } from "vue";
import type { MockupAsset } from "~/types/mockup";
import { getProductLabel } from "~/utils/mockupProducts";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import MockupProductTabs from "~/components/workflow/production/MockupProductTabs.vue";
import MockupCard from "~/components/workflow/production/MockupCard.vue";
import MockupEmptyState from "~/components/workflow/production/MockupEmptyState.vue";
import MockupProductPickerModal from "~/components/workflow/production/MockupProductPickerModal.vue";

defineProps<{
  availableTabs: string[];
  selectedTab: string;
  mockupsByProduct: Record<string, MockupAsset[]>;
  currentTabMockups: MockupAsset[];
  totalMockupsCount: number;
  renderNonce: number;
  isActionLoading?: boolean;
  actionError?: string | null;
  campaignProducts?: string[];
  aiSuggestedProducts?: string[];
}>();

const emit = defineEmits<{
  (e: "selectTab", tab: string): void;
  (e: "openAddMockup", product: string): void;
  (e: "adjustPlacement", asset: MockupAsset): void;
  (e: "setCover", asset: MockupAsset): void;
  (e: "delete", asset: MockupAsset): void;
  (e: "move", asset: MockupAsset, dir: "up" | "down"): void;
}>();

const showProductPickerModal = ref(false);
const previewingAsset = ref<MockupAsset | null>(null);

function handleOpenAddMockup(product: string): void {
  emit("openAddMockup", product);
}

function handleSelectProductFromPicker(productKey: string): void {
  showProductPickerModal.value = false;
  emit("openAddMockup", productKey);
}
</script>

<template>
  <div class="space-y-4">
    <!-- Gallery Section Header -->
    <div class="flex items-center justify-between">
      <div>
        <h4 class="text-sm font-bold text-foreground flex items-center gap-2">
          <Icon name="lucide:images" class="size-4 text-primary" aria-hidden="true" />
          <span>Product Mockups</span>
          <span v-if="totalMockupsCount > 0" class="text-xs text-muted-foreground font-normal">({{ totalMockupsCount }} listing {{ totalMockupsCount === 1 ? 'mockup' : 'mockups' }})</span>
        </h4>
        <p class="text-xs text-muted-foreground">
          Upload blank mockup templates or photos to preview your master artwork on realistic products.
        </p>
      </div>

      <Button
        v-if="availableTabs.length === 0"
        variant="default"
        size="sm"
        class="font-bold gap-1.5 shadow-xs cursor-pointer inline-flex items-center"
        :disabled="isActionLoading"
        @click="showProductPickerModal = true"
      >
        <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
        <span>Add Mockup</span>
      </Button>
    </div>

    <!-- Error Banner -->
    <Alert v-if="actionError" variant="destructive" class="py-2.5">
      <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
      <div>
        <AlertTitle class="text-xs font-bold">Action Failed</AlertTitle>
        <AlertDescription class="text-xs">{{ actionError }}</AlertDescription>
      </div>
    </Alert>

    <!-- When Active Mockups Exist: Show dynamic product tabs and active grid -->
    <div v-if="availableTabs.length > 0" class="space-y-4">
      <MockupProductTabs
        :available-tabs="availableTabs"
        :selected-tab="selectedTab"
        :mockups-by-product="mockupsByProduct"
        @select-tab="(tab) => emit('selectTab', tab)"
        @open-new-category="showProductPickerModal = true"
      />

      <!-- Tab Sub-Header -->
      <div class="flex items-center justify-between pt-1">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-foreground">
            {{ getProductLabel(selectedTab) }}
          </span>
          <span class="text-xs text-muted-foreground">
            ({{ currentTabMockups.length }} listing {{ currentTabMockups.length === 1 ? 'mockup' : 'mockups' }})
          </span>
        </div>

        <Button
          variant="outline"
          size="sm"
          class="text-xs font-semibold gap-1.5 h-8 cursor-pointer"
          :disabled="isActionLoading"
          @click="handleOpenAddMockup(selectedTab)"
        >
          <Icon name="lucide:plus" class="size-3" aria-hidden="true" />
          <span>Add Another {{ getProductLabel(selectedTab) }}</span>
        </Button>
      </div>

      <!-- Mockups Grid -->
      <div v-if="currentTabMockups.length > 0" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <MockupCard
          v-for="(asset, idx) in currentTabMockups"
          :key="asset.id"
          :asset="asset"
          :index="idx"
          :total-in-tab="currentTabMockups.length"
          :product-label="getProductLabel(selectedTab)"
          :render-nonce="renderNonce"
          :is-action-loading="isActionLoading"
          @set-cover="(a) => emit('setCover', a)"
          @adjust-placement="(a) => emit('adjustPlacement', a)"
          @delete="(a) => emit('delete', a)"
          @move="(a, dir) => emit('move', a, dir)"
          @preview="(a) => previewingAsset = a"
        />
      </div>

      <!-- Empty Tab Fallback -->
      <MockupEmptyState
        v-else
        :product-label="getProductLabel(selectedTab)"
        :is-action-loading="isActionLoading"
        @add-mockup="handleOpenAddMockup(selectedTab)"
      />
    </div>

    <!-- Generic Single Empty State When Zero Mockups Exist Across All Categories -->
    <MockupEmptyState
      v-else
      :is-action-loading="isActionLoading"
      @add-mockup="showProductPickerModal = true"
    />

    <!-- Product Picker Modal -->
    <MockupProductPickerModal
      :open="showProductPickerModal"
      :existing-categories="availableTabs"
      :campaign-products="campaignProducts"
      :ai-suggested-products="aiSuggestedProducts"
      :mockups-by-product="mockupsByProduct"
      @close="showProductPickerModal = false"
      @select="handleSelectProductFromPicker"
    />

    <!-- Zoom Preview Modal -->
    <div
      v-if="previewingAsset"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs"
      @click="previewingAsset = null"
    >
      <div class="relative max-w-3xl max-h-[85vh] bg-zinc-950 rounded-2xl overflow-hidden shadow-2xl p-2 border border-zinc-800" @click.stop>
        <button
          type="button"
          class="absolute top-4 right-4 z-10 h-8 w-8 rounded-full bg-black/60 hover:bg-black text-white flex items-center justify-center backdrop-blur-xs transition-colors cursor-pointer"
          @click="previewingAsset = null"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
        <img
          :src="previewingAsset.url || ''"
          :alt="previewingAsset.provenance?.template_name || 'Mockup Preview'"
          class="w-full h-full object-contain max-h-[80vh] rounded-xl"
        >
        <div class="p-3 text-center text-xs text-zinc-400 font-medium">
          {{ previewingAsset.provenance?.template_name || 'Listing Mockup Preview' }}
        </div>
      </div>
    </div>
  </div>
</template>
