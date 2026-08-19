<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { ShopSection } from '~/types/listing';
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
  <div class="rounded-xl border border-border bg-card text-card-foreground shadow-xs p-5 space-y-5" data-testid="shop-organization-card">
    <div class="flex items-center justify-between border-b border-border/60 pb-3">
      <div class="flex items-center gap-2.5">
        <div class="flex size-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-200">
          <Icon name="lucide:folder-tree" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-foreground">Shop Organization &amp; Renewal</h3>
          <p class="text-2xs text-muted-foreground">Etsy shop section and automatic renewal preferences</p>
        </div>
      </div>

      <Button
        v-if="isDirty"
        type="button"
        size="sm"
        variant="default"
        :disabled="isSaving"
        class="text-xs h-7 px-2.5 gap-1.5 cursor-pointer"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:check" class="size-3" aria-hidden="true" />
        <span>Save</span>
      </Button>
    </div>

    <!-- Shop Section Selector -->
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <Label for="shop-section" class="text-xs font-medium flex items-center gap-1.5">
          <Icon name="lucide:layers" class="size-3.5 text-muted-foreground" aria-hidden="true" />
          <span>Etsy Shop Section</span>
        </Label>
        <button
          type="button"
          class="text-2xs text-primary hover:underline flex items-center gap-1 cursor-pointer"
          @click="showNewSectionInput = !showNewSectionInput"
        >
          <Icon name="lucide:plus" class="size-3" aria-hidden="true" />
          <span>{{ showNewSectionInput ? 'Cancel' : '+ New Section' }}</span>
        </button>
      </div>

      <!-- Existing Sections Dropdown -->
      <select
        id="shop-section"
        :value="localSectionId || ''"
        class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        @change="onSelectSection"
      >
        <option value="">-- No Section (General Storefront) --</option>
        <option v-for="sec in sections" :key="sec.shop_section_id" :value="sec.shop_section_id">
          {{ sec.title }} ({{ sec.active_listing_count }} active)
        </option>
      </select>

      <div v-if="localSectionName && !localSectionId" class="text-2xs text-amber-700 bg-amber-50 px-2 py-1 rounded border border-amber-200">
        Suggested section: <strong>{{ localSectionName }}</strong> (Will be assigned upon creation)
      </div>

      <!-- New Section Inline Input Form -->
      <div v-if="showNewSectionInput" class="flex items-center gap-2 pt-1">
        <Input
          v-model="newSectionTitle"
          type="text"
          placeholder="e.g. Christmas PNGs, Sublimation Bundles"
          maxlength="120"
          class="h-8 text-xs flex-1"
          @keyup.enter="handleCreateSection"
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          :disabled="isCreatingSection || !newSectionTitle.trim()"
          class="h-8 px-2.5 text-xs gap-1 cursor-pointer"
          @click="handleCreateSection"
        >
          <Icon v-if="isCreatingSection" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
          <span>Create</span>
        </Button>
      </div>
    </div>

    <!-- Renewal Mode Option -->
    <div class="space-y-2 pt-1 border-t border-border/40">
      <Label class="text-xs font-medium flex items-center gap-1.5">
        <Icon name="lucide:refresh-cw" class="size-3.5 text-muted-foreground" aria-hidden="true" />
        <span>Etsy Renewal Preference</span>
      </Label>

      <div class="grid grid-cols-2 gap-2">
        <button
          type="button"
          class="flex flex-col text-left p-2.5 rounded-lg border text-xs transition-all cursor-pointer"
          :class="!localAutoRenew ? 'border-primary bg-primary/5 text-foreground ring-1 ring-primary' : 'border-border bg-card text-muted-foreground hover:border-slate-300'"
          @click="onAutoRenewToggle(false)"
        >
          <span class="font-semibold text-xs flex items-center gap-1.5">
            <Icon name="lucide:pause-circle" class="size-3.5 text-slate-500" aria-hidden="true" />
            Manual Renewal
          </span>
          <span class="text-2xs text-muted-foreground mt-0.5">Expires after 4 months unless renewed</span>
        </button>

        <button
          type="button"
          class="flex flex-col text-left p-2.5 rounded-lg border text-xs transition-all cursor-pointer"
          :class="localAutoRenew ? 'border-primary bg-primary/5 text-foreground ring-1 ring-primary' : 'border-border bg-card text-muted-foreground hover:border-slate-300'"
          @click="onAutoRenewToggle(true)"
        >
          <span class="font-semibold text-xs flex items-center gap-1.5">
            <Icon name="lucide:repeat" class="size-3.5 text-emerald-600" aria-hidden="true" />
            Automatic Renewal
          </span>
          <span class="text-2xs text-muted-foreground mt-0.5">Renews automatically when expired ($0.20 fee)</span>
        </button>
      </div>
    </div>
  </div>
</template>
