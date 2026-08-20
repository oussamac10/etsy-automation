<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import Input from '~/components/ui/Input.vue';
import Dialog from '~/components/ui/Dialog.vue';
import DialogHeader from '~/components/ui/DialogHeader.vue';
import DialogTitle from '~/components/ui/DialogTitle.vue';
import DialogDescription from '~/components/ui/DialogDescription.vue';
import DialogFooter from '~/components/ui/DialogFooter.vue';
import type { ReResolveTaxonomyResponse, TaxonomyCategory, TaxonomyFitness } from '~/types/listing';

const props = defineProps<{
  workflowId: string;
  taxonomyId?: number | null;
  taxonomyPath?: string | null;
  taxonomySelectionSource?: 'auto' | 'manual' | 'fallback' | string | null;
  isUpdating?: boolean;
}>();

const emit = defineEmits<{
  (e: 'updateCategory', payload: { id: number; path: string }): void;
  (e: 'reResolved', payload: ReResolveTaxonomyResponse): void;
}>();

const isModalOpen = ref(false);
const searchQuery = ref('');
const searchResults = ref<TaxonomyCategory[]>([]);
const isLoadingResults = ref(false);
const isReResolving = ref(false);
const selectedNode = ref<{ id: number; path: string } | null>(null);

const activeFitness = ref<TaxonomyFitness | null>(null);
const isLoadingFitness = ref(false);

const currentPath = computed(() => props.taxonomyPath || '');
const currentId = computed(() => props.taxonomyId || null);

const RECOMMENDED_CATEGORIES: TaxonomyCategory[] = [
  {
    id: 77,
    name: 'Digital',
    full_path: 'Art & Collectibles > Drawing & Illustration > Digital',
    level: 2,
  },
  {
    id: 2078,
    name: 'Digital Prints',
    full_path: 'Art & Collectibles > Prints > Digital Prints',
    level: 2,
  },
  {
    id: 6844,
    name: 'Clip Art & Image Files',
    full_path: 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files',
    level: 3,
  },
];

function getApiBase(): string {
  try {
    const config = useRuntimeConfig();
    return config?.public?.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';
  } catch {
    return '';
  }
}

async function loadFitness() {
  if (!props.workflowId || !props.taxonomyId) {
    activeFitness.value = null;
    return;
  }
  isLoadingFitness.value = true;
  try {
    const apiBase = getApiBase();
    const data = await $fetch<TaxonomyFitness>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy/fitness`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    activeFitness.value = data || null;
  } catch {
    activeFitness.value = null;
  } finally {
    isLoadingFitness.value = false;
  }
}

async function loadCategories(query?: string) {
  isLoadingResults.value = true;
  try {
    const apiBase = getApiBase();
    const url = query
      ? `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy/categories?q=${encodeURIComponent(query)}`
      : `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy/categories`;
    const data = await $fetch<TaxonomyCategory[]>(url, {
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });
    searchResults.value = data || [];
  } catch {
    searchResults.value = RECOMMENDED_CATEGORIES;
  } finally {
    isLoadingResults.value = false;
  }
}

async function reResolveTaxonomy(apply = false) {
  if (!props.workflowId) return;
  isReResolving.value = true;
  try {
    const apiBase = getApiBase();
    const res = await $fetch<ReResolveTaxonomyResponse>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy/re-resolve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        credentials: 'include',
        body: { apply },
      }
    );
    emit('reResolved', res);
    if (apply) {
      emit('updateCategory', {
        id: res.recommended_taxonomy_id,
        path: res.recommended_taxonomy_path,
      });
    }
    await loadFitness();
    await loadCategories();
  } catch {
    // Graceful fallback
  } finally {
    isReResolving.value = false;
  }
}

function openModal() {
  selectedNode.value = currentId.value
    ? {
        id: currentId.value,
        path: currentPath.value,
      }
    : null;
  searchQuery.value = '';
  isModalOpen.value = true;
  loadCategories();
}

function selectCategory(cat: TaxonomyCategory) {
  selectedNode.value = {
    id: cat.id,
    path: cat.full_path,
  };
}

function confirmSelection() {
  if (selectedNode.value) {
    emit('updateCategory', selectedNode.value);
    isModalOpen.value = false;
  }
}

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(searchQuery, (newQuery) => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    loadCategories(newQuery.trim());
  }, 300);
});

watch(
  () => [props.workflowId, props.taxonomyId],
  () => {
    loadFitness();
  }
);

onMounted(() => {
  loadFitness();
});

defineExpose({
  openModal,
  loadFitness,
  reResolveTaxonomy,
});
</script>

<template>
  <Card class="border-border bg-card shadow-xs self-start" data-testid="etsy-category-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:folder-tree" class="size-4 text-primary" aria-hidden="true" />
          <span>Etsy Seller Category</span>
        </CardTitle>
        <CardDescription class="text-xs">
          Etsy Open API v3 seller taxonomy for digital transparent PNG artwork.
        </CardDescription>
      </div>
      <div class="flex items-center gap-2 shrink-0 self-start sm:self-auto">
        <Button
          v-if="props.taxonomyId"
          variant="ghost"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer"
          :disabled="isReResolving"
          @click="reResolveTaxonomy(false)"
        >
          <Icon v-if="isReResolving" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:refresh-cw" class="size-3.5" aria-hidden="true" />
          <span>Re-evaluate</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer"
          @click="openModal"
        >
          <Icon name="lucide:sliders-horizontal" class="size-3.5" aria-hidden="true" />
          <span>{{ props.taxonomyId ? 'Change Category' : 'Select Category' }}</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-3">
      <!-- Empty state when no category is selected -->
      <div
        v-if="!props.taxonomyId"
        class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg bg-muted/20 border border-dashed border-border text-xs"
        data-testid="empty-category-state"
      >
        <div class="space-y-0.5">
          <p class="font-medium text-foreground">No category selected</p>
          <p class="text-2xs text-muted-foreground">Select an Etsy seller category to configure taxonomy attributes for this campaign.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer self-start sm:self-auto"
          @click="openModal"
        >
          <Icon name="lucide:sliders-horizontal" class="size-3.5" aria-hidden="true" />
          <span>Select Category</span>
        </Button>
      </div>

      <!-- Selected category info -->
      <div v-else class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg bg-muted/40 border border-border/70 text-xs">
        <div class="flex items-start gap-2.5 min-w-0">
          <Icon name="lucide:check-circle-2" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div class="min-w-0">
            <p class="font-medium text-foreground truncate" :title="currentPath">
              {{ currentPath }}
            </p>
            <p class="text-2xs text-muted-foreground mt-0.5">
              Taxonomy ID: <code class="font-mono text-foreground font-semibold">{{ currentId }}</code> • Item Type: <span class="font-medium text-foreground">Digital Download</span>
            </p>
          </div>
        </div>
        <div class="flex items-center gap-1.5 shrink-0 self-start sm:self-auto flex-wrap">
          <!-- Poor fit status badge -->
          <Badge
            v-if="activeFitness?.has_mismatched_required_attributes || activeFitness?.blocking_mismatch || (activeFitness?.fit_score !== undefined && activeFitness.fit_score < 0.5)"
            variant="outline"
            class="text-2xs py-0.5 gap-1 font-mono font-semibold bg-amber-100 text-amber-950 dark:bg-amber-950/80 dark:text-amber-200 border-amber-300 dark:border-amber-700"
          >
            <Icon name="lucide:alert-triangle" class="size-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>Poor fit</span>
          </Badge>

          <!-- Fitness indicator for good/moderate fit -->
          <Badge
            v-else-if="activeFitness && activeFitness.fit_score !== undefined && activeFitness.fit_level !== 'unknown'"
            variant="outline"
            class="text-2xs py-0.5 gap-1 font-mono font-semibold bg-emerald-100 text-emerald-950 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700"
          >
            <Icon name="lucide:sparkles" class="size-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>{{ Math.round(activeFitness.fit_score * 100) }}% fit</span>
          </Badge>

          <!-- Source badge -->
          <Badge v-if="props.taxonomySelectionSource === 'manual'" variant="outline" class="bg-blue-100 text-blue-950 dark:bg-blue-950/80 dark:text-blue-200 border-blue-300 dark:border-blue-700 text-2xs py-0.5 font-semibold">
            Manual override
          </Badge>
          <Badge v-else-if="props.taxonomySelectionSource === 'fallback'" variant="outline" class="bg-amber-100 text-amber-950 dark:bg-amber-950/80 dark:text-amber-200 border-amber-300 dark:border-amber-700 text-2xs py-0.5 font-semibold">
            Fallback — review required
          </Badge>
          <Badge
            v-else-if="!(activeFitness?.has_mismatched_required_attributes || activeFitness?.blocking_mismatch || (activeFitness?.fit_score !== undefined && activeFitness.fit_score < 0.5))"
            variant="outline"
            class="bg-primary/10 text-primary border-primary/20 text-2xs py-0.5 font-semibold"
          >
            Auto-selected
          </Badge>
        </div>
      </div>

      <!-- Poor fit warning callout -->
      <div
        v-if="props.taxonomyId && (activeFitness?.has_mismatched_required_attributes || activeFitness?.blocking_mismatch || (activeFitness?.fit_score !== undefined && activeFitness.fit_score < 0.5))"
        class="text-[11px] text-amber-950 dark:text-amber-200 flex items-center gap-1.5 px-1 font-medium bg-amber-50/70 dark:bg-amber-950/30 p-2 rounded-md border border-amber-200 dark:border-amber-800"
      >
        <Icon name="lucide:alert-triangle" class="size-3.5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        <span>Required attributes do not match this campaign's intended use.</span>
      </div>

      <!-- Fit reasons callout if compatible -->
      <div v-else-if="props.taxonomyId && activeFitness?.fit_reasons && activeFitness.fit_reasons.length > 0" class="text-[10px] text-muted-foreground flex items-center gap-1.5 flex-wrap px-1">
        <span class="font-semibold text-foreground/80 uppercase tracking-wider text-[9px]">Compatibility:</span>
        <span v-for="(reason, idx) in activeFitness.fit_reasons.slice(0, 2)" :key="idx" class="inline-flex items-center gap-1">
          <span>• {{ reason }}</span>
        </span>
      </div>
    </CardContent>

    <!-- Change Category Modal -->
    <Dialog :open="isModalOpen" @close="isModalOpen = false">
      <DialogHeader>
        <DialogTitle class="text-base font-semibold flex items-center gap-2">
          <Icon name="lucide:folder-tree" class="size-4 text-primary" aria-hidden="true" />
          Select Etsy Digital Category
        </DialogTitle>
        <DialogDescription class="text-xs">
          Choose the official Etsy seller taxonomy category that best matches your digital transparent PNG product. Physical product categories (plates, mugs, apparel) are disqualified.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">
        <div class="relative">
          <Icon name="lucide:search" class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" aria-hidden="true" />
          <Input
            v-model="searchQuery"
            placeholder="Search digital categories (e.g. clip art, digital prints, stickers)..."
            class="pl-9 text-xs h-9"
          />
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between text-2xs font-semibold text-muted-foreground uppercase tracking-wider px-1">
            <span>{{ searchQuery ? 'Search Results' : 'Recommended Digital Categories' }}</span>
            <span v-if="isLoadingResults" class="flex items-center gap-1 text-primary">
              <Icon name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
              Searching...
            </span>
          </div>

          <div class="max-h-64 overflow-y-auto space-y-1.5 pr-1">
            <button
              v-for="cat in searchResults"
              :key="cat.id"
              type="button"
              class="w-full text-left p-3 rounded-lg border transition-colors flex flex-col gap-1 text-xs"
              :class="[
                selectedNode?.id === cat.id
                  ? 'bg-primary/10 border-primary text-foreground font-medium'
                  : 'bg-card hover:bg-muted/50 border-border text-muted-foreground'
              ]"
              @click="selectCategory(cat)"
            >
              <div class="flex items-center justify-between gap-3 w-full">
                <div class="min-w-0">
                  <p class="font-medium text-foreground truncate">{{ cat.name }}</p>
                  <p class="text-2xs text-muted-foreground truncate">{{ cat.full_path }}</p>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <Badge
                    v-if="cat.fit_score !== undefined && cat.fit_score !== null"
                    variant="outline"
                    class="font-mono text-2xs py-0 font-semibold"
                    :class="
                      cat.fit_score >= 0.8
                        ? 'bg-emerald-100 text-emerald-950 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700'
                        : cat.fit_score < 0.5
                        ? 'bg-amber-100 text-amber-950 dark:bg-amber-950/80 dark:text-amber-200 border-amber-300 dark:border-amber-700'
                        : 'bg-muted text-foreground'
                    "
                  >
                    {{ Math.round(cat.fit_score * 100) }}% fit
                  </Badge>
                  <Badge
                    v-else
                    variant="outline"
                    class="text-2xs py-0 text-muted-foreground font-medium"
                  >
                    Fitness unavailable
                  </Badge>
                  <Badge variant="outline" class="font-mono text-2xs py-0 font-medium">ID: {{ cat.id }}</Badge>
                  <Icon
                    v-if="selectedNode?.id === cat.id"
                    name="lucide:check"
                    class="size-4 text-primary shrink-0"
                    aria-hidden="true"
                  />
                </div>
              </div>

              <!-- Badges / Reasons in card item -->
              <div v-if="(cat.fit_reasons && cat.fit_reasons.length > 0) || (cat.warnings && cat.warnings.length > 0)" class="flex items-center gap-1.5 flex-wrap mt-1">
                <span
                  v-for="(r, idx) in (cat.fit_reasons || []).slice(0, 2)"
                  :key="'r-' + idx"
                  class="text-[10px] font-semibold text-emerald-950 dark:text-emerald-200 bg-emerald-100 dark:bg-emerald-950/80 border border-emerald-300 dark:border-emerald-800 px-1.5 py-0.5 rounded"
                >
                  ✓ {{ r }}
                </span>
                <span
                  v-for="(w, idx) in (cat.warnings || []).slice(0, 1)"
                  :key="'w-' + idx"
                  class="text-[10px] font-semibold text-amber-950 dark:text-amber-200 bg-amber-100 dark:bg-amber-950/80 border border-amber-300 dark:border-amber-800 px-1.5 py-0.5 rounded"
                >
                  ⚠ {{ w }}
                </span>
              </div>
            </button>

            <div
              v-if="!isLoadingResults && searchResults.length === 0"
              class="py-6 text-center text-xs text-muted-foreground"
            >
              No matching digital categories found for "{{ searchQuery }}".
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="flex items-center justify-between sm:justify-between pt-3 border-t">
        <Button variant="ghost" size="sm" class="text-xs" @click="isModalOpen = false">
          Cancel
        </Button>
        <Button
          size="sm"
          class="text-xs gap-1.5"
          :disabled="!selectedNode || props.isUpdating"
          @click="confirmSelection"
        >
          <Icon v-if="props.isUpdating" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
          Apply Category
        </Button>
      </DialogFooter>
    </Dialog>
  </Card>
</template>
