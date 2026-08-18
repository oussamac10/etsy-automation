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
  isSaving: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:tags', value: string[]): void;
  (e: 'save'): void;
}>();

const localTags = ref<string[]>([...props.tags]);
const newTagInput = ref('');
const inputError = ref<string | null>(null);

watch(() => props.tags, (newVal) => {
  localTags.value = [...newVal];
});

const tagCount = computed(() => localTags.value.length);
const isComplete = computed(() => tagCount.value === MAX_ETSY_TAGS);
const isUnderLimit = computed(() => tagCount.value < MAX_ETSY_TAGS);

const normalizedNewTag = computed(() => normalizeTag(newTagInput.value));
const newTagLength = computed(() => normalizedNewTag.value.length);
const isNewTagTooLong = computed(() => newTagLength.value > MAX_TAG_LENGTH);

const hasUnsavedChanges = computed(() => {
  if (localTags.value.length !== props.tags.length) return true;
  return JSON.stringify(localTags.value) !== JSON.stringify(props.tags);
});

function addTag() {
  inputError.value = null;
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
  localTags.value.splice(index, 1);
  emit('update:tags', [...localTags.value]);
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    addTag();
  }
}
</script>

<template>
  <Card class="border-border shadow-xs">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:tags" class="size-4 text-primary" aria-hidden="true" />
          <span>Etsy SEO Tags</span>
          <Badge
            :variant="isComplete ? 'success' : (isUnderLimit ? 'warning' : 'destructive')"
            class="text-[11px] font-mono font-bold"
          >
            {{ tagCount }} / {{ MAX_ETSY_TAGS }} tags
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          Exactly 13 tags required for optimal Etsy discovery. Max 20 characters per tag.
        </CardDescription>
      </div>

      <Button
        v-if="hasUnsavedChanges"
        type="button"
        variant="default"
        size="sm"
        :disabled="isSaving || !isComplete"
        class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer self-start sm:self-auto shrink-0"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
        <span>Save</span>
      </Button>
    </CardHeader>

    <CardContent class="space-y-3 pt-0">
      <!-- Tag Badges List -->
      <div class="flex flex-wrap gap-1.5 min-h-12 p-2.5 bg-slate-50/80 border border-slate-200/80 rounded-lg">
        <div
          v-for="(tag, idx) in localTags"
          :key="tag + idx"
          class="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-white border border-slate-200 text-slate-800 shadow-2xs hover:border-slate-300 transition-all touch-manipulation"
        >
          <span class="font-mono text-[10px] text-muted-foreground">{{ idx + 1 }}.</span>
          <span class="font-sans">{{ tag }}</span>
          <button
            type="button"
            class="text-slate-400 hover:text-destructive transition-colors ml-0.5 p-0.5 cursor-pointer focus-visible:outline-none"
            title="Remove tag"
            @click="removeTag(idx)"
          >
            <Icon name="lucide:x" class="size-3" aria-hidden="true" />
          </button>
        </div>

        <div v-if="localTags.length === 0" class="flex items-center justify-center w-full py-2 text-xs text-muted-foreground italic">
          No tags added yet. Enter a tag below or generate automatically.
        </div>
      </div>

      <!-- Add Tag Input Bar -->
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <div class="relative flex-1">
            <Input
              v-model="newTagInput"
              :disabled="tagCount >= MAX_ETSY_TAGS"
              placeholder="Add an Etsy tag (e.g. sublimation design)..."
              class="text-xs h-9 pr-14"
              :error="isNewTagTooLong"
              @keydown="handleKeyDown"
            />
            <span
              v-if="newTagInput.trim()"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-mono"
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
            class="text-xs h-9 px-3 gap-1 cursor-pointer"
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
        <p v-else-if="!isComplete" class="text-[11px] text-amber-600 font-medium flex items-center gap-1">
          <Icon name="lucide:info" class="size-3" aria-hidden="true" />
          <span>{{ MAX_ETSY_TAGS - tagCount }} more tag{{ MAX_ETSY_TAGS - tagCount === 1 ? '' : 's' }} needed to reach exactly 13 Etsy tags.</span>
        </p>
      </div>
    </CardContent>
  </Card>
</template>
