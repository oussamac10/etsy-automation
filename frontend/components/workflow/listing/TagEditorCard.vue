<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Badge from '~/components/ui/Badge.vue';
import { MAX_ETSY_TAGS, MAX_TAG_LENGTH, normalizeTag, validateTag } from '~/utils/tags';

const props = defineProps<{
  tags: string[];
  tagHistory?: string[];
  isSaving: boolean;
  hasUnsavedChanges?: boolean;
  isDeletingTagHistory?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:tags', value: string[]): void;
  (e: 'save'): void;
  (e: 'deleteHistoryTag', tag: string): void;
}>();

const localTags = ref<string[]>([...props.tags]);
const localRemovedTags = ref<string[]>([]);
const newTagInput = ref('');
const inputError = ref<string | null>(null);
const restoreNotice = ref<string | null>(null);

// History filter & search (closed by default)
const isHistoryExpanded = ref(false);
const historySearchQuery = ref('');
const historyFilter = ref<'all' | 'removed' | 'active'>('all');

// Synchronize with external tags
watch(
  () => props.tags,
  (newVal) => {
    localTags.value = [...newVal];
  },
  { deep: true }
);

// Reset local removed tags when history prop changes (e.g. campaign switch)
watch(
  () => props.tagHistory,
  () => {
    localRemovedTags.value = [];
  },
  { deep: true }
);

const tagCount = computed(() => localTags.value.length);
const isComplete = computed(() => tagCount.value === MAX_ETSY_TAGS);
const isUnderLimit = computed(() => tagCount.value < MAX_ETSY_TAGS);

const normalizedNewTag = computed(() => normalizeTag(newTagInput.value));
const newTagLength = computed(() => normalizedNewTag.value.length);
const isNewTagTooLong = computed(() => newTagLength.value > MAX_TAG_LENGTH);

const isDirty = computed(() => {
  if (props.hasUnsavedChanges !== undefined) return props.hasUnsavedChanges;
  if (localTags.value.length !== props.tags.length) return true;
  return JSON.stringify(localTags.value) !== JSON.stringify(props.tags);
});

// All-time aggregated history for this campaign
const allCampaignHistory = computed<string[]>(() => {
  const set = new Set<string>();
  const list: string[] = [];

  const add = (t: string) => {
    const clean = normalizeTag(t);
    if (clean && !set.has(clean)) {
      set.add(clean);
      list.push(clean);
    }
  };

  // 1. Tags in current prop / draft
  for (const t of props.tags || []) add(t);
  // 2. Tags in local state
  for (const t of localTags.value || []) add(t);
  // 3. Tags explicitly removed in this session
  for (const t of localRemovedTags.value || []) add(t);
  // 4. Tags in persisted campaign tag history
  for (const t of props.tagHistory || []) add(t);

  return list;
});

// Filtered history list
const filteredHistory = computed(() => {
  let list = allCampaignHistory.value;

  const currentSet = new Set(localTags.value.map((t) => normalizeTag(t)));

  if (historyFilter.value === 'removed') {
    list = list.filter((t) => !currentSet.has(t));
  } else if (historyFilter.value === 'active') {
    list = list.filter((t) => currentSet.has(t));
  }

  if (historySearchQuery.value.trim()) {
    const q = historySearchQuery.value.toLowerCase().trim();
    list = list.filter((t) => t.toLowerCase().includes(q));
  }

  return list;
});

const removedCount = computed(() => {
  const currentSet = new Set(localTags.value.map((t) => normalizeTag(t)));
  return allCampaignHistory.value.filter((t) => !currentSet.has(t)).length;
});

const activeCount = computed(() => {
  const currentSet = new Set(localTags.value.map((t) => normalizeTag(t)));
  return allCampaignHistory.value.filter((t) => currentSet.has(t)).length;
});

function addTag() {
  inputError.value = null;
  restoreNotice.value = null;
  const raw = newTagInput.value.trim();
  if (!raw) return;

  if (localTags.value.length >= MAX_ETSY_TAGS) {
    inputError.value = `Etsy allows a maximum of ${MAX_ETSY_TAGS} tags.`;
    return;
  }

  const { isValid, error } = validateTag(raw, localTags.value);
  if (!isValid) {
    inputError.value = error || 'Invalid tag.';
    return;
  }

  const normalized = normalizeTag(raw);
  localTags.value.push(normalized);
  newTagInput.value = '';
  emit('update:tags', [...localTags.value]);
}

function removeTag(index: number) {
  const removed = localTags.value[index];
  if (removed) {
    const norm = normalizeTag(removed);
    if (!localRemovedTags.value.includes(norm)) {
      localRemovedTags.value.unshift(norm);
    }
  }
  localTags.value.splice(index, 1);
  emit('update:tags', [...localTags.value]);
}

function restoreTag(tag: string) {
  inputError.value = null;
  restoreNotice.value = null;

  const normalized = normalizeTag(tag);
  if (localTags.value.some((t) => normalizeTag(t) === normalized)) {
    return; // Already active
  }

  if (localTags.value.length >= MAX_ETSY_TAGS) {
    restoreNotice.value = `Cannot restore "${tag}": Maximum of ${MAX_ETSY_TAGS} tags reached. Remove an active tag first.`;
    setTimeout(() => {
      if (restoreNotice.value?.includes(tag)) restoreNotice.value = null;
    }, 4500);
    return;
  }

  const { isValid, error } = validateTag(normalized, localTags.value);
  if (!isValid) {
    inputError.value = error || 'Cannot restore this tag.';
    return;
  }

  localTags.value.push(normalized);
  emit('update:tags', [...localTags.value]);
}

function restoreAllAvailable() {
  inputError.value = null;
  restoreNotice.value = null;

  const currentSet = new Set(localTags.value.map((t) => normalizeTag(t)));
  const available = allCampaignHistory.value.filter((t) => !currentSet.has(t));

  const slots = MAX_ETSY_TAGS - localTags.value.length;
  if (slots <= 0) {
    restoreNotice.value = `All ${MAX_ETSY_TAGS} tag slots are currently full.`;
    return;
  }

  const toAdd = available.slice(0, slots);
  for (const t of toAdd) {
    localTags.value.push(t);
  }
  emit('update:tags', [...localTags.value]);
}

function deleteFromHistory(tag: string) {
  const norm = normalizeTag(tag);
  localRemovedTags.value = localRemovedTags.value.filter((t) => t !== norm);
  emit('deleteHistoryTag', norm);
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    addTag();
  }
}
</script>

<template>
  <Card class="border-border shadow-xs overflow-hidden">
    <!-- Header -->
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:tags" class="size-4 text-primary" aria-hidden="true" />
          <span>Etsy SEO Tags</span>
          <Badge
            :variant="isComplete ? 'default' : (isUnderLimit ? 'secondary' : 'destructive')"
            class="text-[11px] font-mono font-bold"
          >
            {{ tagCount }} / {{ MAX_ETSY_TAGS }} tags
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          Exactly 13 tags required for optimal Etsy search ranking. Max 20 characters per tag.
        </CardDescription>
      </div>

      <Button
        v-if="isDirty"
        type="button"
        variant="default"
        size="sm"
        :disabled="isSaving || !isComplete"
        class="text-xs h-8 px-3 gap-1.5 cursor-pointer self-start sm:self-auto shrink-0 font-bold"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
        <span>Save Tags</span>
      </Button>
    </CardHeader>

    <CardContent class="space-y-4 pt-0">
      <!-- Active Tags Box -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-xs text-muted-foreground px-0.5">
          <span class="font-medium text-foreground text-[11px] uppercase tracking-wider">Active Campaign Tags</span>
          <span class="font-mono tabular-nums text-[11px]">
            {{ tagCount }} of {{ MAX_ETSY_TAGS }} slots filled
          </span>
        </div>

        <div class="flex flex-wrap gap-1.5 min-h-12 p-3 bg-secondary/30 border border-border/80 rounded-xl">
          <div
            v-for="(tag, idx) in localTags"
            :key="tag + idx"
            class="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-white border border-border text-foreground shadow-2xs hover:border-slate-300 transition-all touch-manipulation animate-in fade-in duration-150"
          >
            <span class="font-mono tabular-nums text-[10px] text-muted-foreground">{{ idx + 1 }}.</span>
            <span>{{ tag }}</span>
            <button
              type="button"
              class="text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xs transition-colors ml-0.5 p-0.5 cursor-pointer focus-visible:outline-none"
              title="Remove tag (moves to campaign history)"
              @click="removeTag(idx)"
            >
              <Icon name="lucide:x" class="size-3" aria-hidden="true" />
            </button>
          </div>

          <div
            v-if="localTags.length === 0"
            class="flex items-center justify-center w-full py-3 text-xs text-muted-foreground italic"
          >
            No active tags yet. Type below, generate with AI, or restore from campaign history.
          </div>
        </div>
      </div>

      <!-- Add Tag Input Bar -->
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <div class="relative flex-1">
            <Input
              v-model="newTagInput"
              :disabled="tagCount >= MAX_ETSY_TAGS"
              placeholder="Add an Etsy tag (e.g. vintage botanical, sublimation art)..."
              class="text-xs h-9 pr-14"
              :error="isNewTagTooLong"
              @keydown="handleKeyDown"
            />
            <span
              v-if="newTagInput.trim()"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-mono tabular-nums"
              :class="isNewTagTooLong ? 'text-destructive font-bold' : 'text-muted-foreground'"
            >
              {{ newTagLength }}/{{ MAX_TAG_LENGTH }}
            </span>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            :disabled="!newTagInput.trim() || isNewTagTooLong || tagCount >= MAX_ETSY_TAGS"
            class="text-xs h-9 px-3 gap-1 cursor-pointer font-semibold"
            @click="addTag"
          >
            <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
            <span>Add</span>
          </Button>
        </div>

        <p v-if="inputError" class="text-[11px] text-destructive font-medium flex items-center gap-1">
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>{{ inputError }}</span>
        </p>
        <p v-else-if="restoreNotice" class="text-[11px] text-foreground font-medium flex items-center gap-1.5 bg-amber-500/10 px-2.5 py-1.5 rounded-md border border-amber-500/30">
          <Icon name="lucide:alert-triangle" class="size-3.5 text-amber-500 shrink-0" aria-hidden="true" />
          <span>{{ restoreNotice }}</span>
        </p>
        <p v-else-if="!isComplete" class="text-[11px] text-muted-foreground flex items-center gap-1">
          <Icon name="lucide:info" class="size-3 text-primary" aria-hidden="true" />
          <span>{{ MAX_ETSY_TAGS - tagCount }} more tag{{ MAX_ETSY_TAGS - tagCount === 1 ? '' : 's' }} needed to reach exactly 13 Etsy tags.</span>
        </p>
      </div>

      <!-- Campaign Tag History & Removed Tags Section -->
      <div class="pt-3 border-t border-border/80 space-y-3">
        <div class="flex items-center justify-between">
          <button
            type="button"
            class="flex items-center gap-2 text-xs font-bold text-foreground hover:text-primary transition-colors cursor-pointer"
            @click="isHistoryExpanded = !isHistoryExpanded"
          >
            <Icon name="lucide:history" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Campaign Tag History & Removed Tags</span>
            <Badge variant="outline" class="text-[10px] font-mono font-bold px-1.5 py-0">
              {{ allCampaignHistory.length }}
            </Badge>
            <Icon
              :name="isHistoryExpanded ? 'lucide:chevron-up' : 'lucide:chevron-down'"
              class="size-3.5 text-muted-foreground"
              aria-hidden="true"
            />
          </button>

          <div v-if="isHistoryExpanded && removedCount > 0 && tagCount < MAX_ETSY_TAGS" class="flex items-center gap-2">
            <button
              type="button"
              class="text-[11px] font-semibold text-primary hover:underline inline-flex items-center gap-1 cursor-pointer"
              @click="restoreAllAvailable"
            >
              <Icon name="lucide:rotate-ccw" class="size-3" aria-hidden="true" />
              <span>Restore Available ({{ Math.min(removedCount, MAX_ETSY_TAGS - tagCount) }})</span>
            </button>
          </div>
        </div>

        <!-- Expanded History Body -->
        <div v-if="isHistoryExpanded" class="space-y-2.5 animate-in fade-in duration-200">
          <p class="text-[11px] text-muted-foreground leading-relaxed">
            Tags created, generated, or removed for <strong>this specific campaign</strong>. Click <strong>+ Restore</strong> on any tag to add it back to your active 13 tags.
          </p>

          <!-- Filter & Search Controls -->
          <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2">
            <!-- Filter Tabs -->
            <div class="inline-flex items-center gap-1 p-0.5 bg-secondary/50 rounded-lg border border-border/60 text-xs">
              <button
                type="button"
                class="px-2 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer"
                :class="historyFilter === 'all' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
                @click="historyFilter = 'all'"
              >
                All History ({{ allCampaignHistory.length }})
              </button>
              <button
                type="button"
                class="px-2 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer"
                :class="historyFilter === 'removed' ? 'bg-white text-foreground shadow-2xs font-bold text-amber-700' : 'text-muted-foreground hover:text-foreground'"
                @click="historyFilter = 'removed'"
              >
                Removed / Inactive ({{ removedCount }})
              </button>
              <button
                type="button"
                class="px-2 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer"
                :class="historyFilter === 'active' ? 'bg-white text-foreground shadow-2xs font-bold text-emerald-700' : 'text-muted-foreground hover:text-foreground'"
                @click="historyFilter = 'active'"
              >
                Active ({{ activeCount }})
              </button>
            </div>

            <!-- Search Input -->
            <div v-if="allCampaignHistory.length > 5" class="relative w-full sm:w-48">
              <Input
                v-model="historySearchQuery"
                placeholder="Search history..."
                class="h-7 text-[11px] pl-7"
              />
              <Icon name="lucide:search" class="size-3 text-muted-foreground absolute left-2 top-1/2 -translate-y-1/2" aria-hidden="true" />
            </div>
          </div>

          <!-- History Tag Chips -->
          <div class="flex flex-wrap gap-1.5 p-3 bg-secondary/40 border border-border rounded-xl max-h-48 overflow-y-auto">
            <div
              v-for="tag in filteredHistory"
              :key="tag"
              class="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-all"
              :class="[
                localTags.some((t) => normalizeTag(t) === tag)
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                  : 'bg-card border-border text-foreground shadow-2xs hover:border-primary/50'
              ]"
            >
              <span class="font-sans">{{ tag }}</span>

              <!-- Active Status Badge -->
              <span
                v-if="localTags.some((t) => normalizeTag(t) === tag)"
                class="inline-flex items-center gap-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 font-mono ml-0.5"
              >
                <Icon name="lucide:check" class="size-3" aria-hidden="true" />
                <span>Active</span>
              </span>

              <!-- Restore Button (if inactive) -->
              <button
                v-else
                type="button"
                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary hover:bg-primary hover:text-white transition-colors cursor-pointer"
                :title="tagCount >= MAX_ETSY_TAGS ? '13 tags maximum reached. Remove a tag first.' : `Restore '${tag}' to active tags`"
                @click="restoreTag(tag)"
              >
                <Icon name="lucide:plus" class="size-2.5" aria-hidden="true" />
                <span>Restore</span>
              </button>

              <!-- Delete From History Button -->
              <button
                type="button"
                class="text-slate-300 hover:text-destructive transition-colors ml-0.5 p-0.5 cursor-pointer opacity-0 group-hover:opacity-100"
                :title="`Delete '${tag}' from campaign history`"
                @click="deleteFromHistory(tag)"
              >
                <Icon name="lucide:trash-2" class="size-3" aria-hidden="true" />
              </button>
            </div>

            <div
              v-if="filteredHistory.length === 0"
              class="flex items-center justify-center w-full py-4 text-xs text-muted-foreground italic"
            >
              <span v-if="historySearchQuery">No historical tags match "{{ historySearchQuery }}".</span>
              <span v-else-if="historyFilter === 'removed'">No removed tags for this campaign. All historical tags are currently active.</span>
              <span v-else>No tag history recorded for this campaign yet.</span>
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
