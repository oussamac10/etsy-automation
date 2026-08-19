<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { TaxonomyProperty } from '~/types/listing';
import Button from '~/components/ui/Button.vue';
import Label from '~/components/ui/Label.vue';

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

    // Pre-fill local properties map if empty and suggestions exist
    if (Object.keys(localPropertiesMap.value).length === 0 && properties.value.length > 0) {
      const initial: Record<string, any> = {};
      for (const p of properties.value) {
        if (p.suggested_values && p.suggested_values.length > 0) {
          initial[String(p.property_id)] = {
            property_id: p.property_id,
            value_ids: p.suggested_value_ids || [],
            values: p.suggested_values || [],
          };
        }
      }
      localPropertiesMap.value = initial;
      emit('update:etsyProperties', initial);
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
  <div class="rounded-xl border border-border bg-card text-card-foreground shadow-xs p-5 space-y-5" data-testid="taxonomy-attributes-card">
    <div class="flex items-center justify-between border-b border-border/60 pb-3">
      <div class="flex items-center gap-2.5">
        <div class="flex size-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-200">
          <Icon name="lucide:sliders-horizontal" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-foreground">Taxonomy Attributes &amp; Properties</h3>
          <p class="text-2xs text-muted-foreground">Category-specific attributes for Etsy search filtering</p>
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

    <!-- Loading State -->
    <div v-if="isLoading" class="space-y-3">
      <div class="h-10 bg-slate-100 animate-pulse rounded-lg" />
      <div class="h-10 bg-slate-100 animate-pulse rounded-lg" />
    </div>

    <!-- Properties List -->
    <div v-else-if="properties.length > 0" class="space-y-4">
      <div
        v-for="prop in properties"
        :key="prop.property_id"
        class="space-y-2 pb-3 border-b border-border/40 last:border-0 last:pb-0"
      >
        <div class="flex items-center justify-between">
          <Label class="text-xs font-medium text-foreground">
            {{ prop.name }}
            <span v-if="prop.is_required" class="text-destructive font-bold">*</span>
          </Label>
          <span class="text-2xs text-muted-foreground">
            {{ prop.is_multivalued ? 'Multi-select' : 'Single select' }}
          </span>
        </div>

        <!-- Predefined possible values pill buttons -->
        <div v-if="prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1.5">
          <button
            v-for="val in prop.possible_values"
            :key="val.value_id || val.name"
            type="button"
            class="inline-flex items-center gap-1 px-2.5 py-1 text-2xs rounded-md border transition-colors cursor-pointer"
            :class="
              isValueSelected(prop.property_id, val.name)
                ? 'bg-primary/10 text-primary border-primary/40 font-medium'
                : 'bg-muted/40 text-muted-foreground border-border hover:bg-muted/80'
            "
            @click="toggleValue(prop, val.name, val.value_id)"
          >
            <Icon
              v-if="isValueSelected(prop.property_id, val.name)"
              name="lucide:check"
              class="size-3 text-primary shrink-0"
              aria-hidden="true"
            />
            <span>{{ val.name }}</span>
          </button>
        </div>

        <!-- Selected values summary if active -->
        <div
          v-if="localPropertiesMap[String(prop.property_id)] && localPropertiesMap[String(prop.property_id)].values.length"
          class="text-2xs text-muted-foreground"
        >
          Selected: <span class="font-medium text-foreground">{{ localPropertiesMap[String(prop.property_id)].values.join(', ') }}</span>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-4 text-xs text-muted-foreground bg-slate-50/50 rounded-lg border border-dashed border-border">
      <Icon name="lucide:info" class="size-4 mx-auto mb-1 text-slate-400" aria-hidden="true" />
      <span>No category-specific properties required for this taxonomy category.</span>
    </div>
  </div>
</template>
