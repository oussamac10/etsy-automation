<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { ShopSection } from '~/types/listing';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Input from '~/components/ui/Input.vue';
import Label from '~/components/ui/Label.vue';

const props = defineProps<{
  workflowId: string;
  shopSectionId?: string | null;
  shopSectionName?: string | null;
  shouldAutoRenew?: boolean;
  isSaving?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:shopSectionId', val: string | null): void;
  (e: 'update:shopSectionName', val: string | null): void;
  (e: 'update:shouldAutoRenew', val: boolean): void;
  (e: 'save'): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

const localSectionId = ref<string | null>(props.shopSectionId || null);
const localSectionName = ref<string | null>(props.shopSectionName || null);
const localAutoRenew = ref<boolean>(props.shouldAutoRenew ?? false);

const sections = ref<ShopSection[]>([]);
const isLoadingSections = ref(false);
const isCreatingSection = ref(false);
const newSectionTitle = ref('');
const showNewSectionInput = ref(false);

watch(
  () => props.shopSectionId,
  (newVal) => {
    localSectionId.value = newVal || null;
  }
);

watch(
  () => props.shopSectionName,
  (newVal) => {
    localSectionName.value = newVal || null;
  }
);

watch(
  () => props.shouldAutoRenew,
  (newVal) => {
    localAutoRenew.value = newVal ?? false;
  }
);

async function loadSections() {
  if (!props.workflowId) return;
  isLoadingSections.value = true;
  try {
    const data = await $fetch<ShopSection[]>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/shop-sections`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    sections.value = Array.isArray(data) ? data : [];
  } catch {
    sections.value = [];
  } finally {
    isLoadingSections.value = false;
  }
}

onMounted(() => {
  loadSections();
});

function onSelectSection(event: Event) {
  const target = event.target as HTMLSelectElement;
  const val = target.value;
  if (!val) {
    localSectionId.value = null;
    localSectionName.value = null;
    emit('update:shopSectionId', null);
    emit('update:shopSectionName', null);
  } else {
    localSectionId.value = val;
    const match = sections.value.find((s) => s.shop_section_id === val);
    const name = match ? match.title : null;
    localSectionName.value = name;
    emit('update:shopSectionId', val);
    emit('update:shopSectionName', name);
  }
}

async function handleCreateSection() {
  if (!newSectionTitle.value.trim() || !props.workflowId) return;
  isCreatingSection.value = true;
  try {
    const created = await $fetch<ShopSection>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/shop-sections`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: { title: newSectionTitle.value.trim() },
        credentials: 'include',
      }
    );
    if (created) {
      sections.value.push(created);
      localSectionId.value = created.shop_section_id;
      localSectionName.value = created.title;
      emit('update:shopSectionId', created.shop_section_id);
      emit('update:shopSectionName', created.title);
      newSectionTitle.value = '';
      showNewSectionInput.value = false;
    }
  } catch {
    // handled gracefully
  } finally {
    isCreatingSection.value = false;
  }
}

function onAutoRenewToggle(val: boolean) {
  localAutoRenew.value = val;
  emit('update:shouldAutoRenew', val);
}

const isDirty = computed(() => {
  return (
    localSectionId.value !== (props.shopSectionId || null) ||
    localSectionName.value !== (props.shopSectionName || null) ||
    localAutoRenew.value !== (props.shouldAutoRenew ?? false)
  );
});
</script>

<template>
  <Card
    class="shadow-xs border border-border/80 bg-card transition-all duration-200"
    data-testid="shop-organization-card"
  >
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/80 text-foreground border border-border/60">
            <Icon name="lucide:folder-tree" class="size-4 text-muted-foreground" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-sm font-semibold">Shop Organization &amp; Renewal</CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Etsy shop section assignment and renewal mode
            </CardDescription>
          </div>
        </div>

        <Button
          v-if="isDirty"
          type="button"
          size="sm"
          variant="default"
          :disabled="isSaving"
          class="text-xs h-7 px-2.5 gap-1.5 cursor-pointer shadow-2xs font-medium"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3" aria-hidden="true" />
          <span>Save</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="pt-4 space-y-4">
      <!-- Shop Section Selector -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label for="shop-section" class="text-xs font-medium text-foreground/90">
            Etsy Shop Section
          </Label>
          <button
            type="button"
            class="text-2xs text-primary hover:underline cursor-pointer font-medium"
            @click="showNewSectionInput = !showNewSectionInput"
          >
            {{ showNewSectionInput ? 'Cancel' : '+ New Section' }}
          </button>
        </div>

        <!-- Inline Section Creator -->
        <div v-if="showNewSectionInput" class="flex gap-2 p-2 rounded-lg bg-muted/30 border border-border/60">
          <Input
            v-model="newSectionTitle"
            type="text"
            placeholder="Section title e.g. Christmas PNGs"
            class="h-8 text-xs bg-background"
            @keydown.enter.prevent="handleCreateSection"
          />
          <Button
            type="button"
            size="sm"
            class="h-8 px-2.5 text-xs shrink-0 cursor-pointer font-medium"
            :disabled="isCreatingSection || !newSectionTitle.trim()"
            @click="handleCreateSection"
          >
            <Icon v-if="isCreatingSection" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
            <span v-else>Add</span>
          </Button>
        </div>

        <!-- Existing Sections Dropdown -->
        <select
          id="shop-section"
          :value="localSectionId || ''"
          class="flex h-8 w-full rounded-md border border-input bg-background px-2.5 py-1 text-xs shadow-2xs transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          @change="onSelectSection"
        >
          <option value="">-- No Section (General Storefront) --</option>
          <option v-for="sec in sections" :key="sec.shop_section_id" :value="sec.shop_section_id">
            {{ sec.title }} ({{ sec.active_listing_count }} active)
          </option>
        </select>
      </div>

      <!-- Renewal Options -->
      <div class="space-y-1.5 pt-1 border-t border-border/40">
        <Label class="text-xs font-medium text-foreground/90">
          Renewal Preference
        </Label>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <!-- Manual Renewal -->
          <button
            type="button"
            class="flex items-start gap-2.5 p-2.5 rounded-lg border text-left transition-colors cursor-pointer"
            :class="!localAutoRenew ? 'border-primary/60 bg-primary/5 text-foreground' : 'border-border/60 bg-card text-muted-foreground hover:bg-muted/40'"
            @click="onAutoRenewToggle(false)"
          >
            <Icon name="lucide:pause-circle" class="size-4 shrink-0 mt-0.5" :class="!localAutoRenew ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
            <div>
              <div class="text-xs font-medium text-foreground">Manual Renewal</div>
              <p class="text-2xs text-muted-foreground mt-0.5 leading-tight">
                Expires after 4 months unless renewed manually.
              </p>
            </div>
          </button>

          <!-- Automatic Renewal -->
          <button
            type="button"
            class="flex items-start gap-2.5 p-2.5 rounded-lg border text-left transition-colors cursor-pointer"
            :class="localAutoRenew ? 'border-primary/60 bg-primary/5 text-foreground' : 'border-border/60 bg-card text-muted-foreground hover:bg-muted/40'"
            @click="onAutoRenewToggle(true)"
          >
            <Icon name="lucide:repeat" class="size-4 shrink-0 mt-0.5" :class="localAutoRenew ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
            <div>
              <div class="text-xs font-medium text-foreground">Automatic Renewal</div>
              <p class="text-2xs text-muted-foreground mt-0.5 leading-tight">
                Auto-renews every 4 months ($0.20 per cycle).
              </p>
            </div>
          </button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
