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
import type { TaxonomyCategory } from '~/types/listing';

const props = defineProps<{
  workflowId: string;
  taxonomyId?: number | null;
  taxonomyPath?: string | null;
  isUpdating?: boolean;
}>();

const emit = defineEmits<{
  (e: 'updateCategory', payload: { id: number; path: string }): void;
}>();

const isModalOpen = ref(false);
const searchQuery = ref('');
const searchResults = ref<TaxonomyCategory[]>([]);
const isLoadingResults = ref(false);
const selectedNode = ref<{ id: number; path: string } | null>(null);

const DEFAULT_CATEGORY_PATH = 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files';
const DEFAULT_CATEGORY_ID = 6844;

const currentPath = computed(() => props.taxonomyPath || DEFAULT_CATEGORY_PATH);
const currentId = computed(() => props.taxonomyId || DEFAULT_CATEGORY_ID);

const RECOMMENDED_CATEGORIES: TaxonomyCategory[] = [
  {
    id: 6844,
    name: 'Clip Art & Image Files',
    full_path: 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files',
    level: 3,
  },
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
    id: 769,
    name: 'Store Graphics',
    full_path: 'Paper & Party Supplies > Paper > Stationery > Design & Templates > Graphic Design > Store Graphics',
    level: 4,
  },
];

async function loadCategories(query?: string) {
  isLoadingResults.value = true;
  try {
    const config = useRuntimeConfig();
    const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';
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

function openModal() {
  selectedNode.value = {
    id: currentId.value,
    path: currentPath.value,
  };
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
</script>

<template>
  <Card class="border-border bg-card shadow-xs self-start" data-testid="etsy-category-card">
    <CardHeader class="p-4 sm:p-5 pb-3">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
            <Icon name="lucide:folder-tree" class="size-4" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <CardTitle class="text-sm font-semibold tracking-tight">Etsy Seller Category</CardTitle>
            <CardDescription class="text-xs text-muted-foreground truncate">
              Etsy Open API v3 seller taxonomy for digital transparent PNG artwork.
            </CardDescription>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium shrink-0"
          @click="openModal"
        >
          <Icon name="lucide:sliders-horizontal" class="size-3.5" aria-hidden="true" />
          Change Category
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg bg-muted/40 border border-border/70 text-xs">
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
        <div class="flex items-center gap-1.5 shrink-0 self-start sm:self-auto">
          <Badge v-if="props.taxonomyId && props.taxonomyId !== DEFAULT_CATEGORY_ID" variant="outline" class="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 text-2xs py-0.5">
            Manual override
          </Badge>
          <Badge v-else variant="outline" class="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-2xs py-0.5">
            Smart match
          </Badge>
        </div>
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

          <div class="max-h-60 overflow-y-auto space-y-1.5 pr-1">
            <button
              v-for="cat in searchResults"
              :key="cat.id"
              type="button"
              class="w-full text-left p-2.5 rounded-lg border transition-colors flex items-center justify-between gap-3 text-xs"
              :class="[
                selectedNode?.id === cat.id
                  ? 'bg-primary/10 border-primary text-foreground font-medium'
                  : 'bg-card hover:bg-muted/50 border-border text-muted-foreground'
              ]"
              @click="selectCategory(cat)"
            >
              <div class="min-w-0">
                <p class="font-medium text-foreground truncate">{{ cat.name }}</p>
                <p class="text-2xs text-muted-foreground truncate">{{ cat.full_path }}</p>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <Badge variant="outline" class="font-mono text-2xs py-0">ID: {{ cat.id }}</Badge>
                <Icon
                  v-if="selectedNode?.id === cat.id"
                  name="lucide:check"
                  class="size-4 text-primary shrink-0"
                  aria-hidden="true"
                />
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
