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
  <Card class="border-border bg-card shadow-xs" data-testid="shop-organization-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:layers" class="size-4 text-primary" aria-hidden="true" />
          <span>Shop Section &amp; Renewal</span>
        </CardTitle>
        <CardDescription class="text-xs">
          Assign Etsy shop section and set listing renewal preference.
        </CardDescription>
      </div>

      <Button
        v-if="isDirty"
        type="button"
        variant="default"
        size="sm"
        :disabled="isSaving"
        class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer self-start sm:self-auto"
        @click="emit('save')"
      >
        <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
        <span>Save</span>
      </Button>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Shop Section Selector -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label for="shop-section" class="text-xs font-semibold text-foreground">
            Etsy Shop Section
          </Label>
          <button
            type="button"
            class="text-[11px] text-primary hover:underline cursor-pointer font-medium"
            @click="showNewSectionInput = !showNewSectionInput"
          >
            {{ showNewSectionInput ? 'Cancel' : '+ New Section' }}
          </button>
        </div>

        <!-- Inline Section Creator -->
        <div v-if="showNewSectionInput" class="flex gap-2 p-2 rounded-lg bg-muted/40 border border-border">
          <Input
            v-model="newSectionTitle"
            type="text"
            placeholder="e.g. Christmas PNGs"
            class="h-8 text-xs bg-background"
            @keydown.enter.prevent="handleCreateSection"
          />
          <Button
            type="button"
            size="sm"
            class="h-8 px-2.5 text-xs shrink-0 cursor-pointer"
            :disabled="isCreatingSection || !newSectionTitle.trim()"
            @click="handleCreateSection"
          >
            <Icon v-if="isCreatingSection" name="lucide:loader-circle" class="size-3 animate-spin" aria-hidden="true" />
            <span v-else>Add</span>
          </Button>
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
      </div>

      <!-- Renewal Mode -->
      <div class="space-y-1.5 pt-1 border-t border-border/40">
        <Label class="text-xs font-semibold text-foreground">
          Renewal Preference
        </Label>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <!-- Manual Renewal -->
          <button
            type="button"
            class="flex items-start gap-2.5 p-3 rounded-lg border text-left transition-colors cursor-pointer"
            :class="!localAutoRenew ? 'border-primary bg-primary/5 text-foreground' : 'border-border bg-card text-muted-foreground hover:border-slate-300'"
            @click="onAutoRenewToggle(false)"
          >
            <Icon name="lucide:pause-circle" class="size-4 shrink-0 mt-0.5 text-primary" aria-hidden="true" />
            <div>
              <div class="text-xs font-semibold text-foreground">Manual Renewal</div>
              <p class="text-[11px] text-muted-foreground mt-0.5 leading-normal">
                Expires after 4 months unless renewed manually.
              </p>
            </div>
          </button>

          <!-- Automatic Renewal -->
          <button
            type="button"
            class="flex items-start gap-2.5 p-3 rounded-lg border text-left transition-colors cursor-pointer"
            :class="localAutoRenew ? 'border-primary bg-primary/5 text-foreground' : 'border-border bg-card text-muted-foreground hover:border-slate-300'"
            @click="onAutoRenewToggle(true)"
          >
            <Icon name="lucide:repeat" class="size-4 shrink-0 mt-0.5 text-primary" aria-hidden="true" />
            <div>
              <div class="text-xs font-semibold text-foreground">Automatic Renewal</div>
              <p class="text-[11px] text-muted-foreground mt-0.5 leading-normal">
                Auto-renews every 4 months ($0.20 per cycle).
              </p>
            </div>
          </button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
