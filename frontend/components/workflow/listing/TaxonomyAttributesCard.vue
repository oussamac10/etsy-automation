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
  <Card
    class="shadow-xs border border-border/80 bg-card transition-all duration-200"
    data-testid="taxonomy-attributes-card"
  >
    <CardHeader class="pb-3 border-b border-border/40">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/80 text-foreground border border-border/60">
            <Icon name="lucide:sliders-horizontal" class="size-4 text-muted-foreground" aria-hidden="true" />
          </div>
          <div>
            <CardTitle class="text-sm font-semibold">Category Attributes</CardTitle>
            <CardDescription class="text-xs text-muted-foreground mt-0.5">
              Attributes for Etsy search filtering
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
      <!-- Loading State Skeleton -->
      <div v-if="isLoading" class="space-y-3">
        <div class="h-10 bg-muted/40 animate-pulse rounded-lg" />
        <div class="h-10 bg-muted/40 animate-pulse rounded-lg" />
      </div>

      <!-- Properties List -->
      <div v-else-if="properties.length > 0" class="space-y-3">
        <div
          v-for="prop in properties"
          :key="prop.property_id"
          class="space-y-1.5 pb-2.5 border-b border-border/40 last:border-0 last:pb-0"
        >
          <div class="flex items-center justify-between">
            <Label class="text-xs font-medium text-foreground/90 flex items-center gap-1">
              <span>{{ prop.name }}</span>
              <span v-if="prop.is_required" class="text-destructive font-bold" title="Required by Etsy">*</span>
            </Label>
            <span class="text-2xs text-muted-foreground font-mono">
              {{ prop.is_multivalued ? 'Multi-select' : 'Single select' }}
            </span>
          </div>

          <!-- Predefined possible values pill buttons -->
          <div v-if="prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1">
            <button
              v-for="val in prop.possible_values"
              :key="val.value_id || val.name"
              type="button"
              class="inline-flex items-center gap-1 px-2 py-0.5 text-2xs rounded border transition-colors cursor-pointer"
              :class="
                isValueSelected(prop.property_id, val.name)
                  ? 'bg-primary text-primary-foreground border-primary font-medium shadow-2xs'
                  : 'bg-muted/30 text-muted-foreground border-border/80 hover:bg-muted/70 hover:text-foreground'
              "
              @click="toggleValue(prop, val.name, val.value_id)"
            >
              <Icon
                :name="isValueSelected(prop.property_id, val.name) ? 'lucide:check' : 'lucide:plus'"
                class="size-2.5"
                aria-hidden="true"
              />
              <span>{{ val.name }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Empty / Fallback State -->
      <div v-else class="text-center py-4 px-3 bg-muted/20 border border-dashed border-border/60 rounded-lg space-y-1">
        <p class="text-xs font-medium text-foreground">Standard Digital Graphic Attributes</p>
        <p class="text-2xs text-muted-foreground">
          Selected taxonomy category accepts standard digital formats (Sublimation, Printing).
        </p>
      </div>
    </CardContent>
  </Card>
</template>
