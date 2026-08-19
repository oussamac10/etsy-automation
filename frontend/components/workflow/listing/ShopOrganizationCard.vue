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
    class="shadow-xs border border-border bg-card transition-all duration-200"
    data-testid="shop-organization-card"
  >
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 border border-indigo-500/20 shadow-2xs">
            <Icon name="lucide:folder-tree" class="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-base font-semibold">Shop Organization &amp; Renewal</CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Etsy shop section discovery, section creation, and renewal settings
            </CardDescription>
          </div>
        </div>

        <Button
          v-if="isDirty"
          type="button"
          size="sm"
          variant="default"
          :disabled="isSaving"
          class="text-xs h-8 px-3 gap-1.5 cursor-pointer shadow-2xs font-medium"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:check" class="size-3.5" aria-hidden="true" />
          <span>Save Changes</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="pt-4 space-y-5">
      <!-- Shop Section Selector -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <Label for="shop-section" class="text-xs font-medium flex items-center gap-1.5 text-foreground">
            <Icon name="lucide:layers" class="size-3.5 text-indigo-500" aria-hidden="true" />
            <span>Etsy Shop Section</span>
          </Label>
          <button
            type="button"
            class="text-2xs text-primary hover:underline flex items-center gap-1 cursor-pointer font-medium"
            @click="showNewSectionInput = !showNewSectionInput"
          >
            <Icon :name="showNewSectionInput ? 'lucide:x' : 'lucide:plus'" class="size-3" aria-hidden="true" />
            <span>{{ showNewSectionInput ? 'Cancel' : '+ Create Section' }}</span>
          </button>
        </div>

        <!-- Inline Section Creator -->
        <div v-if="showNewSectionInput" class="flex gap-2 p-2 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
          <Input
            v-model="newSectionTitle"
            type="text"
            placeholder="e.g., Christmas PNGs or Sublimation Bundles"
            class="h-8 text-xs bg-background"
            @keydown.enter.prevent="handleCreateSection"
          />
          <Button
            type="button"
            size="sm"
            class="h-8 px-3 text-xs shrink-0 cursor-pointer font-medium"
            :disabled="isCreatingSection || !newSectionTitle.trim()"
            @click="handleCreateSection"
          >
            <Icon v-if="isCreatingSection" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
            <span v-else>Create</span>
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
        <p class="text-2xs text-muted-foreground">
          Assigned to the listing draft so buyers can easily browse themed collections in your shop.
        </p>
      </div>

      <!-- Renewal Options Cards -->
      <div class="space-y-2 pt-1 border-t border-border/40">
        <Label class="text-xs font-medium flex items-center gap-1.5 text-foreground">
          <Icon name="lucide:rotate-cw" class="size-3.5 text-indigo-500" aria-hidden="true" />
          <span>Listing Renewal Mode</span>
        </Label>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Manual Renewal Card -->
          <button
            type="button"
            class="flex items-start gap-3 p-3 rounded-xl border text-left transition-all cursor-pointer shadow-2xs"
            :class="!localAutoRenew ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border bg-muted/20 hover:bg-muted/40'"
            @click="onAutoRenewToggle(false)"
          >
            <div class="flex size-7 shrink-0 items-center justify-center rounded-lg" :class="!localAutoRenew ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'">
              <Icon name="lucide:pause-circle" class="size-4" aria-hidden="true" />
            </div>
            <div>
              <div class="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <span>Manual Renewal</span>
                <span v-if="!localAutoRenew" class="text-2xs bg-primary/20 text-primary px-1.5 py-0.2 rounded font-mono">Selected</span>
              </div>
              <p class="text-2xs text-muted-foreground mt-0.5 leading-tight">
                Expires after 4 months unless manually renewed. Gives full control over expired items.
              </p>
            </div>
          </button>

          <!-- Automatic Renewal Card -->
          <button
            type="button"
            class="flex items-start gap-3 p-3 rounded-xl border text-left transition-all cursor-pointer shadow-2xs"
            :class="localAutoRenew ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border bg-muted/20 hover:bg-muted/40'"
            @click="onAutoRenewToggle(true)"
          >
            <div class="flex size-7 shrink-0 items-center justify-center rounded-lg" :class="localAutoRenew ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'">
              <Icon name="lucide:repeat" class="size-4" aria-hidden="true" />
            </div>
            <div>
              <div class="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <span>Automatic Renewal</span>
                <span v-if="localAutoRenew" class="text-2xs bg-primary/20 text-primary px-1.5 py-0.2 rounded font-mono">Selected</span>
              </div>
              <p class="text-2xs text-muted-foreground mt-0.5 leading-tight">
                Automatically renews every 4 months ($0.20 fee) to keep the listing live seamlessly.
              </p>
            </div>
          </button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
