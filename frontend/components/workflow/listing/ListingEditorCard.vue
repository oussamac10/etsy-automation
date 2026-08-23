<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Textarea from '~/components/ui/Textarea.vue';
import Label from '~/components/ui/Label.vue';
import Badge from '~/components/ui/Badge.vue';
import Dialog from '~/components/ui/Dialog.vue';
import DialogHeader from '~/components/ui/DialogHeader.vue';
import DialogTitle from '~/components/ui/DialogTitle.vue';
import DialogDescription from '~/components/ui/DialogDescription.vue';
import DialogFooter from '~/components/ui/DialogFooter.vue';
import type { ListingVersionSnapshot } from '~/types/listing';
import { MAX_TITLE_LENGTH, countSequentialCapitalWords, sanitizeEtsyTitle } from '~/utils/tags';

const MAX_SUMMARY_LENGTH = 200;

const props = defineProps<{
  title: string;
  description: string;
  shoppingCartSummary?: string | null;
  aiDisclosure?: string | null;
  version: number;
  etsyListingId?: string | null;
  isSaving: boolean;
  isUpdatingEtsyDraft?: boolean;
  isGeneratingSeo: boolean;
  generatingTarget?: string | null;
  hasUnsavedChanges?: boolean;
  history?: ListingVersionSnapshot[];
  isRestoringVersion?: boolean;
  isDeletingVersion?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:title', value: string): void;
  (e: 'update:description', value: string): void;
  (e: 'update:shoppingCartSummary', value: string): void;
  (e: 'save'): void;
  (e: 'updateEtsyDraft'): void;
  (e: 'generateSeo', target?: string): void;
  (e: 'restoreVersion', version: number): void;
  (e: 'deleteVersion', version: number): void;
}>();

const localTitle = ref(props.title);
const localDescription = ref(props.description);
const localSummary = ref(props.shoppingCartSummary || '');
const isHistoryOpen = ref(false);

watch(() => props.title, (newVal) => {
  localTitle.value = newVal;
});

watch(() => props.description, (newVal) => {
  localDescription.value = newVal;
});

watch(() => props.shoppingCartSummary, (newVal) => {
  localSummary.value = newVal || '';
});

const titleLength = computed(() => localTitle.value.length);
const isTitleOverLimit = computed(() => titleLength.value > MAX_TITLE_LENGTH);
const isTitleApproachingLimit = computed(() => titleLength.value > 120 && !isTitleOverLimit.value);
const titleCapsWords = computed(() => countSequentialCapitalWords(localTitle.value));
const isTitleCapsOverLimit = computed(() => titleCapsWords.value > 3);

const summaryLength = computed(() => localSummary.value.length);
const isSummaryOverLimit = computed(() => summaryLength.value > MAX_SUMMARY_LENGTH);
const isSummaryApproachingLimit = computed(() => summaryLength.value > 180 && !isSummaryOverLimit.value);

function handleAutoFixTitle() {
  const fixed = sanitizeEtsyTitle(localTitle.value);
  handleTitleUpdate(fixed);
}

const isDirty = computed(() => {
  if (props.hasUnsavedChanges !== undefined) return props.hasUnsavedChanges;
  return (
    localTitle.value !== props.title ||
    localDescription.value !== props.description ||
    localSummary.value !== (props.shoppingCartSummary || '')
  );
});

const versionList = computed(() => {
  const list = props.history || [];
  return [...list].sort((a, b) => b.version - a.version);
});

function handleTitleUpdate(val: string | number) {
  const str = String(val);
  localTitle.value = str;
  emit('update:title', str);
}

function handleDescUpdate(val: string | number) {
  const str = String(val);
  localDescription.value = str;
  emit('update:description', str);
}

function handleSummaryUpdate(val: string | number) {
  const str = String(val);
  localSummary.value = str;
  emit('update:shoppingCartSummary', str);
}

function handleRestore(versionNumber: number) {
  emit('restoreVersion', versionNumber);
  isHistoryOpen.value = false;
}

function formatSnapshotDate(dateStr?: string) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}
</script>

<template>
  <Card class="border-border shadow-xs">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:file-edit" class="size-4 text-primary" aria-hidden="true" />
          <span>Listing Copy & Specifications</span>
          <div class="flex items-center gap-1.5">
            <Badge variant="outline" class="text-[10px] font-mono">v{{ version }}</Badge>
            <Button
              v-if="versionList.length > 0"
              type="button"
              variant="ghost"
              size="sm"
              class="h-5 px-1.5 text-[11px] text-muted-foreground hover:text-foreground gap-1 cursor-pointer"
              @click="isHistoryOpen = true"
            >
              <Icon name="lucide:history" class="size-3 text-muted-foreground" aria-hidden="true" />
              <span>{{ versionList.length }} {{ versionList.length === 1 ? 'version' : 'versions' }}</span>
            </Button>
          </div>
        </CardTitle>
        <CardDescription class="text-xs">
          High-converting Etsy title, structured description, and concise cart summary.
        </CardDescription>
      </div>

      <div class="flex items-center gap-2 self-start sm:self-auto shrink-0 flex-wrap">
        <Button
          type="button"
          variant="outline"
          size="sm"
          :disabled="isGeneratingSeo || isSaving || isRestoringVersion"
          class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer"
          @click="emit('generateSeo', 'all')"
        >
          <Icon v-if="isGeneratingSeo && (!generatingTarget || generatingTarget === 'all')" name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
          <Icon v-else name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Regenerate All</span>
        </Button>

        <Button
          type="button"
          variant="default"
          size="sm"
          :disabled="isSaving || isGeneratingSeo || isRestoringVersion || !isDirty || isTitleOverLimit || isSummaryOverLimit"
          class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="space-y-5 pt-0">
      <!-- 1. Title Field -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <Label for="listing-title" class="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <span>Etsy Listing Title</span>
              <span class="text-muted-foreground font-normal">(Max 140 chars)</span>
            </Label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              :disabled="isGeneratingSeo || isSaving"
              class="h-5 px-1.5 text-[10px] text-muted-foreground hover:text-primary gap-1 cursor-pointer"
              title="Regenerate only the listing title"
              @click="emit('generateSeo', 'title')"
            >
              <Icon v-if="isGeneratingSeo && generatingTarget === 'title'" name="lucide:loader-circle" class="size-2.5 animate-spin text-primary" aria-hidden="true" />
              <Icon v-else name="lucide:sparkles" class="size-2.5 text-primary" aria-hidden="true" />
              <span>Regenerate Title</span>
            </Button>
          </div>

          <span
            class="text-[11px] font-mono tabular-nums font-medium shrink-0"
            :class="{
              'text-destructive font-bold': isTitleOverLimit,
              'text-amber-600': isTitleApproachingLimit,
              'text-muted-foreground': !isTitleOverLimit && !isTitleApproachingLimit,
            }"
          >
            {{ titleLength }} / {{ MAX_TITLE_LENGTH }}
          </span>
        </div>

        <Input
          id="listing-title"
          :model-value="localTitle"
          maxlength="160"
          placeholder="e.g. Vintage Mushroom PNG, Cottagecore Botanical Sublimation Design, Wild Floral Clipart, DTG T-Shirt Download"
          class="text-sm font-medium"
          :error="isTitleOverLimit || isTitleCapsOverLimit"
          @update:model-value="handleTitleUpdate"
        />

        <p v-if="isTitleOverLimit" class="text-[11px] text-destructive font-medium flex items-center gap-1">
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Etsy limits titles to 140 characters. Please shorten before saving.</span>
        </p>

        <!-- Etsy All-Caps / Acronyms Limit Warning with Auto-Fix -->
        <transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 -translate-y-1"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-150 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 -translate-y-1"
        >
          <div
            v-if="isTitleCapsOverLimit"
            class="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-2.5 text-xs"
          >
            <div class="flex items-center gap-2 min-w-0">
              <Icon name="lucide:circle-alert" class="size-4 shrink-0 text-amber-500" aria-hidden="true" />
              <span class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-tight">
                Etsy allows at most 3 words starting with sequential capital letters (found <strong class="tabular-nums">{{ titleCapsWords }}</strong>).
              </span>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-6 px-2 text-[11px] font-medium shrink-0 text-primary hover:bg-primary/10 cursor-pointer"
              @click="handleAutoFixTitle"
            >
              Auto-Fix
            </Button>
          </div>
        </transition>
      </div>

      <!-- 2. Shopping Cart Summary (Dedicated Field) -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <Label for="listing-summary" class="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <span>Shopping Cart Summary</span>
              <span class="text-muted-foreground font-normal">(Max 200 chars)</span>
            </Label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              :disabled="isGeneratingSeo || isSaving"
              class="h-5 px-1.5 text-[10px] text-muted-foreground hover:text-primary gap-1 cursor-pointer"
              title="Regenerate only the shopping cart summary"
              @click="emit('generateSeo', 'shopping_cart_summary')"
            >
              <Icon v-if="isGeneratingSeo && generatingTarget === 'shopping_cart_summary'" name="lucide:loader-circle" class="size-2.5 animate-spin text-primary" aria-hidden="true" />
              <Icon v-else name="lucide:sparkles" class="size-2.5 text-primary" aria-hidden="true" />
              <span>Regenerate Summary</span>
            </Button>
          </div>

          <span
            class="text-[11px] font-mono tabular-nums font-medium shrink-0"
            :class="{
              'text-destructive font-bold': isSummaryOverLimit,
              'text-amber-600': isSummaryApproachingLimit,
              'text-muted-foreground': !isSummaryOverLimit && !isSummaryApproachingLimit,
            }"
          >
            {{ summaryLength }} / {{ MAX_SUMMARY_LENGTH }}
          </span>
        </div>

        <Textarea
          id="listing-summary"
          :model-value="localSummary"
          :rows="2"
          placeholder="e.g. Cute kawaii medical equipment PNG with MRI and CT scanner characters in pastel colors. High-res 4500x5400 px transparent file for shirts, scrubs, stickers and sublimation."
          class="text-xs font-normal leading-relaxed font-sans"
          @update:model-value="handleSummaryUpdate"
        />

        <p v-if="isSummaryOverLimit" class="text-[11px] text-destructive font-medium flex items-center gap-1">
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Etsy limits cart summary to 200 characters. Please shorten before saving.</span>
        </p>
      </div>

      <!-- 3. Description Field -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <Label for="listing-desc" class="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <span>Product Description</span>
            </Label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              :disabled="isGeneratingSeo || isSaving"
              class="h-5 px-1.5 text-[10px] text-muted-foreground hover:text-primary gap-1 cursor-pointer"
              title="Regenerate only the structured description"
              @click="emit('generateSeo', 'description')"
            >
              <Icon v-if="isGeneratingSeo && generatingTarget === 'description'" name="lucide:loader-circle" class="size-2.5 animate-spin text-primary" aria-hidden="true" />
              <Icon v-else name="lucide:sparkles" class="size-2.5 text-primary" aria-hidden="true" />
              <span>Regenerate Description</span>
            </Button>
          </div>

          <span class="text-[11px] text-muted-foreground">Markdown & sections structured</span>
        </div>

        <Textarea
          id="listing-desc"
          :model-value="localDescription"
          :rows="11"
          placeholder="Structured description stating DIGITAL DOWNLOAD – PNG FILE ONLY, WHAT YOU WILL RECEIVE (dimensions, DPI, transparent background), PERFECT FOR uses, INSTANT DOWNLOAD instructions, COMMERCIAL USE, and AI DISCLOSURE."
          class="text-xs font-normal leading-relaxed font-sans"
          @update:model-value="handleDescUpdate"
        />
      </div>

      <!-- AI Disclosure Banner -->
      <div v-if="aiDisclosure" class="bg-secondary/40 border border-border rounded-lg p-2.5 flex items-start gap-2 text-xs">
        <Icon name="lucide:bot" class="size-4 text-muted-foreground shrink-0 mt-0.5" aria-hidden="true" />
        <div class="space-y-0.5">
          <p class="font-semibold text-foreground text-[11px]">Etsy AI Content Disclosure</p>
          <p class="text-muted-foreground text-[11px] leading-normal">{{ aiDisclosure }}</p>
        </div>
      </div>
    </CardContent>

    <!-- Version History Dialog -->
    <Dialog :open="isHistoryOpen" max-width="2xl" @close="isHistoryOpen = false">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Icon name="lucide:history" class="size-5 text-primary" aria-hidden="true" />
          <span>Listing Copy Version History</span>
        </DialogTitle>
        <DialogDescription>
          Review previous AI-generated and manually edited listing versions. Click restore to switch back to any version anytime.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-3 max-h-[60vh] overflow-y-auto pr-1 py-1">
        <div
          v-for="item in versionList"
          :key="item.version"
          class="p-3.5 rounded-lg border transition-colors flex flex-col gap-2.5"
          :class="item.version === version ? 'bg-primary/5 border-primary/40' : 'bg-card border-border hover:border-primary/40'"
        >
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2">
              <Badge :variant="item.version === version ? 'default' : 'outline'" class="font-mono text-xs">
                v{{ item.version }}
              </Badge>
              <Badge v-if="item.source === 'ai_generated'" variant="secondary" class="gap-1 text-[10px] bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30">
                <Icon name="lucide:sparkles" class="size-2.5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                <span>AI Generated</span>
              </Badge>
              <Badge v-else-if="item.source === 'manual'" variant="secondary" class="gap-1 text-[10px] bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30">
                <Icon name="lucide:pencil" class="size-2.5 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                <span>Manual Edit</span>
              </Badge>
              <Badge v-else variant="outline" class="text-[10px] text-muted-foreground">
                <span>Initial Draft</span>
              </Badge>
              <span v-if="item.created_at" class="text-[11px] text-muted-foreground">
                {{ formatSnapshotDate(item.created_at) }}
              </span>
            </div>

            <div class="flex items-center gap-1.5">
              <Badge v-if="item.version === version" variant="success" class="text-[10px] gap-1">
                <Icon name="lucide:check" class="size-3" aria-hidden="true" />
                <span>Active Version</span>
              </Badge>
              <template v-else>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  :disabled="isRestoringVersion || isDeletingVersion"
                  class="h-7 px-2.5 text-xs gap-1.5 cursor-pointer"
                  @click="handleRestore(item.version)"
                >
                  <Icon v-if="isRestoringVersion" name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
                  <Icon v-else name="lucide:rotate-ccw" class="size-3 text-primary" aria-hidden="true" />
                  <span>Restore v{{ item.version }}</span>
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  :disabled="isRestoringVersion || isDeletingVersion"
                  class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10 cursor-pointer"
                  title="Delete this version"
                  @click="emit('deleteVersion', item.version)"
                >
                  <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
                </Button>
              </template>
            </div>
          </div>

          <div class="space-y-1 bg-muted/40 p-2.5 rounded border border-border/60 text-xs">
            <p class="font-medium text-foreground line-clamp-2">
              <span class="text-muted-foreground font-normal">Title: </span>{{ item.title }}
            </p>
            <p v-if="item.shopping_cart_summary" class="text-muted-foreground text-[11px] line-clamp-2">
              <span class="font-medium text-foreground">Cart Summary: </span>{{ item.shopping_cart_summary }}
            </p>
            <p class="text-muted-foreground text-[11px] line-clamp-2">
              <span class="font-medium text-foreground">Description: </span>{{ item.description }}
            </p>
            <div v-if="item.tags && item.tags.length > 0" class="pt-1 flex flex-wrap gap-1">
              <span
                v-for="tg in item.tags.slice(0, 7)"
                :key="tg"
                class="inline-block px-1.5 py-0.5 rounded bg-card border border-border text-[10px] text-foreground font-mono"
              >
                #{{ tg }}
              </span>
              <span v-if="item.tags.length > 7" class="text-[10px] text-muted-foreground self-center">
                +{{ item.tags.length - 7 }} more
              </span>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="mt-3">
        <Button type="button" variant="outline" size="sm" @click="isHistoryOpen = false">
          Close
        </Button>
      </DialogFooter>
    </Dialog>
  </Card>
</template>
