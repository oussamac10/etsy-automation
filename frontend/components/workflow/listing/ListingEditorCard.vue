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
import { MAX_TITLE_LENGTH } from '~/utils/tags';

const props = defineProps<{
  title: string;
  description: string;
  aiDisclosure?: string | null;
  version: number;
  isSaving: boolean;
  isGeneratingSeo: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:title', value: string): void;
  (e: 'update:description', value: string): void;
  (e: 'save'): void;
  (e: 'generateSeo'): void;
}>();

const localTitle = ref(props.title);
const localDescription = ref(props.description);

watch(() => props.title, (newVal) => {
  localTitle.value = newVal;
});

watch(() => props.description, (newVal) => {
  localDescription.value = newVal;
});

const titleLength = computed(() => localTitle.value.length);
const isTitleOverLimit = computed(() => titleLength.value > MAX_TITLE_LENGTH);
const isTitleApproachingLimit = computed(() => titleLength.value > 120 && !isTitleOverLimit.value);

const hasUnsavedChanges = computed(() => {
  return localTitle.value !== props.title || localDescription.value !== props.description;
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
</script>

<template>
  <Card class="border-border shadow-xs">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:file-edit" class="size-4 text-primary" aria-hidden="true" />
          <span>Listing Copy & Specifications</span>
          <Badge variant="outline" class="text-[10px] font-mono">v{{ version }}</Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          High-converting Etsy title, description, and buyer clarity guidelines.
        </CardDescription>
      </div>

      <div class="flex items-center gap-2 self-start sm:self-auto shrink-0">
        <Button
          type="button"
          variant="outline"
          size="sm"
          :disabled="isGeneratingSeo || isSaving"
          class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer"
          @click="emit('generateSeo')"
        >
          <Icon v-if="isGeneratingSeo" name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
          <Icon v-else name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
          <span>AI Generate</span>
        </Button>

        <Button
          type="button"
          variant="default"
          size="sm"
          :disabled="isSaving || isGeneratingSeo || !hasUnsavedChanges || isTitleOverLimit"
          class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="space-y-4 pt-0">
      <!-- Title Field -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label for="listing-title" class="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <span>Etsy Listing Title</span>
            <span class="text-muted-foreground font-normal">(Max 140 chars)</span>
          </Label>
          <span
            class="text-[11px] font-mono font-medium"
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
          placeholder="e.g. Vintage Mushroom PNG Digital Download, Cottagecore Botanical Sublimation T-Shirt Design"
          class="text-sm font-medium"
          :error="isTitleOverLimit"
          @update:model-value="handleTitleUpdate"
        />
        <p v-if="isTitleOverLimit" class="text-[11px] text-destructive font-medium flex items-center gap-1">
          <Icon name="lucide:circle-alert" class="size-3" aria-hidden="true" />
          <span>Etsy limits titles to 140 characters. Please shorten before saving.</span>
        </p>
      </div>

      <!-- Description Field -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label for="listing-desc" class="text-xs font-semibold text-foreground">
            Product Description
          </Label>
          <span class="text-[11px] text-muted-foreground">Markdown supported</span>
        </div>

        <Textarea
          id="listing-desc"
          :model-value="localDescription"
          :rows="7"
          placeholder="Detailed description stating this is a digital download, specifications (4500x5400 px, 300 DPI, transparent background), uses, and commercial license terms."
          class="text-xs font-normal leading-relaxed font-sans"
          @update:model-value="handleDescUpdate"
        />
      </div>

      <!-- AI Disclosure Banner -->
      <div v-if="aiDisclosure" class="bg-slate-50 border border-slate-200 rounded-lg p-2.5 flex items-start gap-2 text-xs">
        <Icon name="lucide:bot" class="size-4 text-slate-500 shrink-0 mt-0.5" aria-hidden="true" />
        <div class="space-y-0.5">
          <p class="font-semibold text-slate-800 text-[11px]">Etsy AI Content Disclosure</p>
          <p class="text-slate-600 text-[11px] leading-normal">{{ aiDisclosure }}</p>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
