<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { TaxonomyProperty } from '~/types/listing';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Label from '~/components/ui/Label.vue';
import Badge from '~/components/ui/Badge.vue';
import Tabs from '~/components/ui/Tabs.vue';
import TabsList from '~/components/ui/TabsList.vue';
import TabsTrigger from '~/components/ui/TabsTrigger.vue';
import TabsContent from '~/components/ui/TabsContent.vue';

const props = defineProps<{
  workflowId: string;
  taxonomyId?: number | null;
  etsyProperties?: Record<string, any> | null;
  isSaving?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:etsyProperties', val: Record<string, any>): void;
  (e: 'save'): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

const properties = ref<TaxonomyProperty[]>([]);
const isLoading = ref(false);
const activeTab = ref<string>('');
const localPropertiesMap = ref<Record<string, { property_id: number; value_ids: number[]; values: string[] }>>(
  props.etsyProperties ? JSON.parse(JSON.stringify(props.etsyProperties)) : {}
);

watch(
  () => props.etsyProperties,
  (newVal) => {
    if (newVal) {
      localPropertiesMap.value = JSON.parse(JSON.stringify(newVal));
    }
  }
);

watch(
  () => props.taxonomyId,
  () => {
    loadTaxonomyProperties();
  }
);

function applyAiSuggestions() {
  if (!properties.value || properties.value.length === 0) return;
  const initial: Record<string, any> = { ...localPropertiesMap.value };

  for (const p of properties.value) {
    if (p.suggested_values && p.suggested_values.length > 0) {
      initial[String(p.property_id)] = {
        property_id: p.property_id,
        value_ids: p.suggested_value_ids || [],
        values: [...p.suggested_values],
      };
    }
  }
  localPropertiesMap.value = initial;
  emit('update:etsyProperties', initial);
}

async function loadTaxonomyProperties() {
  if (!props.workflowId) return;
  isLoading.value = true;
  try {
    const data = await $fetch<TaxonomyProperty[]>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy-properties`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    properties.value = Array.isArray(data) ? data : [];

    if (properties.value.length > 0) {
      activeTab.value = String(properties.value[0].property_id);
    }

    // Auto-select AI recommended properties if no selections saved yet
    if (Object.keys(localPropertiesMap.value).length === 0 && properties.value.length > 0) {
      applyAiSuggestions();
    }
  } catch {
    properties.value = [];
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => {
  loadTaxonomyProperties();
});

function isValueSelected(propId: number, valName: string): boolean {
  const entry = localPropertiesMap.value[String(propId)];
  if (!entry || !entry.values) return false;
  return entry.values.includes(valName);
}

function isAiSuggested(prop: TaxonomyProperty, valName: string): boolean {
  return Boolean(prop.suggested_values && prop.suggested_values.includes(valName));
}

function getSelectedCount(propId: number): number {
  const entry = localPropertiesMap.value[String(propId)];
  return entry?.values?.length || 0;
}

function toggleValue(prop: TaxonomyProperty, valName: string, valId?: number) {
  const key = String(prop.property_id);
  const current = localPropertiesMap.value[key] || {
    property_id: prop.property_id,
    value_ids: [],
    values: [],
  };

  const values = [...(current.values || [])];
  const valueIds = [...(current.value_ids || [])];

  const idx = values.indexOf(valName);
  if (idx >= 0) {
    values.splice(idx, 1);
    if (valId !== undefined) {
      const idIdx = valueIds.indexOf(valId);
      if (idIdx >= 0) valueIds.splice(idIdx, 1);
    }
  } else {
    if (prop.is_multivalued) {
      values.push(valName);
      if (valId !== undefined) valueIds.push(valId);
    } else {
      values.splice(0, values.length, valName);
      if (valId !== undefined) valueIds.splice(0, valueIds.length, valId);
    }
  }

  if (values.length === 0) {
    delete localPropertiesMap.value[key];
  } else {
    localPropertiesMap.value[key] = {
      property_id: prop.property_id,
      value_ids: valueIds,
      values: values,
    };
  }

  emit('update:etsyProperties', { ...localPropertiesMap.value });
}

const isDirty = computed(() => {
  return JSON.stringify(localPropertiesMap.value) !== JSON.stringify(props.etsyProperties || {});
});
</script>

<template>
  <Card class="border-border bg-card shadow-xs" data-testid="taxonomy-attributes-card">
    <CardHeader class="p-4 sm:p-5 pb-3">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
            <Icon name="lucide:sliders-horizontal" class="size-4" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <CardTitle class="text-sm font-semibold tracking-tight flex items-center gap-2">
              <span>Category Attributes</span>
              <Badge variant="outline" class="text-[10px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20">
                AI Auto-Selected
              </Badge>
            </CardTitle>
            <CardDescription class="text-xs text-muted-foreground truncate">
              Etsy category properties automatically populated by AI for max search visibility.
            </CardDescription>
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <Button
            v-if="properties.length > 0"
            type="button"
            variant="outline"
            size="sm"
            class="h-8 gap-1.5 text-xs font-medium cursor-pointer"
            title="Auto-select AI recommended choices for all attributes"
            @click="applyAiSuggestions"
          >
            <Icon name="lucide:sparkles" class="size-3.5 text-primary" aria-hidden="true" />
            <span class="hidden sm:inline">AI Auto-Fill</span>
          </Button>

          <Button
            v-if="isDirty"
            type="button"
            variant="default"
            size="sm"
            :disabled="isSaving"
            class="h-8 gap-1.5 text-xs font-medium cursor-pointer"
            @click="emit('save')"
          >
            <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
            <span>Save</span>
          </Button>
        </div>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Loading State Skeleton -->
      <div v-if="isLoading" class="space-y-3">
        <div class="h-9 bg-slate-100 animate-pulse rounded-lg" />
        <div class="h-16 bg-slate-100 animate-pulse rounded-lg" />
      </div>

      <!-- Properties Tabs Layout -->
      <div v-else-if="properties.length > 0" class="space-y-3">
        <Tabs v-model="activeTab" class="w-full">
          <TabsList class="w-full justify-start overflow-x-auto h-9 p-1 bg-muted/60">
            <TabsTrigger
              v-for="prop in properties"
              :key="prop.property_id"
              :value="String(prop.property_id)"
              class="text-xs px-2.5 py-1 gap-1.5 shrink-0"
            >
              <span>{{ prop.name }}</span>
              <span v-if="prop.is_required" class="text-destructive font-bold">*</span>
              <Badge
                v-if="getSelectedCount(prop.property_id) > 0"
                variant="secondary"
                class="text-[10px] px-1 py-0 h-4 font-mono font-medium"
              >
                {{ getSelectedCount(prop.property_id) }}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent
            v-for="prop in properties"
            :key="prop.property_id"
            :value="String(prop.property_id)"
            class="pt-3 space-y-2 focus-visible:outline-none"
          >
            <div class="flex items-center justify-between">
              <Label class="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <span>{{ prop.name }}</span>
                <span v-if="prop.is_required" class="text-destructive font-bold" title="Required by Etsy">*</span>
              </Label>
              <div class="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span v-if="prop.suggested_values?.length" class="text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
                  <Icon name="lucide:sparkles" class="size-3" aria-hidden="true" />
                  AI Suggested: {{ prop.suggested_values.join(', ') }}
                </span>
                <span>{{ prop.is_multivalued ? '(Multi-select)' : '(Single select)' }}</span>
              </div>
            </div>

            <!-- Attribute Pills -->
            <div v-if="prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1.5 pt-1">
              <button
                v-for="val in prop.possible_values"
                :key="val.value_id || val.name"
                type="button"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border transition-colors cursor-pointer"
                :class="
                  isValueSelected(prop.property_id, val.name)
                    ? 'bg-primary/10 text-primary border-primary/40 font-semibold'
                    : isAiSuggested(prop, val.name)
                    ? 'bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
                    : 'bg-muted/40 text-muted-foreground border-border hover:bg-muted'
                "
                @click="toggleValue(prop, val.name, val.value_id)"
              >
                <Icon
                  :name="isValueSelected(prop.property_id, val.name) ? 'lucide:check' : isAiSuggested(prop, val.name) ? 'lucide:sparkles' : 'lucide:plus'"
                  class="size-3"
                  :class="isAiSuggested(prop, val.name) && !isValueSelected(prop.property_id, val.name) ? 'text-emerald-600 dark:text-emerald-400' : ''"
                  aria-hidden="true"
                />
                <span>{{ val.name }}</span>
                <span
                  v-if="isAiSuggested(prop, val.name) && !isValueSelected(prop.property_id, val.name)"
                  class="text-[9px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-500/20 px-1 py-0.2 rounded"
                >
                  AI
                </span>
              </button>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <!-- Empty / Fallback State -->
      <div v-else class="text-center py-4 px-3 bg-muted/40 border border-dashed border-border rounded-lg space-y-1">
        <p class="text-xs font-semibold text-foreground">Standard Digital Graphic Attributes</p>
        <p class="text-[11px] text-muted-foreground">
          Selected taxonomy category accepts standard digital formats (Sublimation, Printing).
        </p>
      </div>
    </CardContent>
  </Card>
</template>
