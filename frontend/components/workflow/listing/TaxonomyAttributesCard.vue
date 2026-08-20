<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import type { TaxonomyFitness, TaxonomyProperty } from '~/types/listing';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Label from '~/components/ui/Label.vue';
import Badge from '~/components/ui/Badge.vue';
import Input from '~/components/ui/Input.vue';

const props = defineProps<{
  workflowId: string;
  taxonomyId?: number | null;
  etsyProperties?: Record<string, any> | null;
  isSaving?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:etsyProperties', val: Record<string, any>): void;
  (e: 'save'): void;
  (e: 'reviewCategory'): void;
}>();

function getApiBase(): string {
  try {
    const config = useRuntimeConfig();
    return config?.public?.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';
  } catch {
    return '';
  }
}

const properties = ref<TaxonomyProperty[]>([]);
const fitness = ref<TaxonomyFitness | null>(null);
const isLoading = ref(false);
const showInfoTooltip = ref(false);
const searchQueryMap = ref<Record<number, string>>({});

const localPropertiesMap = ref<Record<string, {
  property_id: number;
  value_ids?: number[];
  values?: string[];
  scale_id?: number;
  scale_name?: string;
  value?: string;
}>>(
  props.etsyProperties ? JSON.parse(JSON.stringify(props.etsyProperties)) : {}
);

watch(
  () => props.etsyProperties,
  (newVal) => {
    localPropertiesMap.value = newVal ? JSON.parse(JSON.stringify(newVal)) : {};
  },
  { deep: true, immediate: true }
);

watch(
  () => [props.workflowId, props.taxonomyId],
  async ([newWf, newTax], [oldWf, oldTax]) => {
    if (newTax !== oldTax && oldTax !== undefined) {
      // Taxonomy switched: clear local state and trigger server reconcile
      localPropertiesMap.value = {};
      emit('update:etsyProperties', {});
    }
    await loadTaxonomyProperties();
    await loadFitness();
    if (newTax !== oldTax && oldTax !== undefined) {
      await reconcileStaleAttributes();
    }
  }
);

// Only keep properties that officially support Etsy listing attributes
const usableProperties = computed(() => {
  return properties.value.filter((p) => p.supports_attributes !== false);
});

async function loadTaxonomyProperties() {
  if (!props.workflowId) return;
  isLoading.value = true;
  try {
    const apiBase = getApiBase();
    const data = await $fetch<TaxonomyProperty[]>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy-properties`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    properties.value = Array.isArray(data) ? data : [];
  } catch {
    properties.value = [];
  } finally {
    isLoading.value = false;
  }
}

async function loadFitness() {
  if (!props.workflowId) return;
  try {
    const apiBase = getApiBase();
    const data = await $fetch<TaxonomyFitness>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy/fitness`,
      {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    fitness.value = data || null;
  } catch {
    fitness.value = null;
  }
}

async function reconcileStaleAttributes() {
  if (!props.workflowId) return;
  try {
    const apiBase = getApiBase();
    const updated = await $fetch<any>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/listing/taxonomy-properties/reconcile`,
      {
        method: 'POST',
        headers: { Accept: 'application/json' },
        credentials: 'include',
      }
    );
    if (updated?.etsy_properties) {
      localPropertiesMap.value = updated.etsy_properties;
      emit('update:etsyProperties', updated.etsy_properties);
    }
  } catch {
    // Ignore reconcile error
  }
}

onMounted(async () => {
  await loadTaxonomyProperties();
  await loadFitness();
});

function getPropertyDisplayName(prop: TaxonomyProperty): string {
  return prop.display_name || prop.name;
}

function isValueSelected(propId: number, valName: string): boolean {
  const entry = localPropertiesMap.value[String(propId)];
  if (!entry || !entry.values) return false;
  return entry.values.includes(valName);
}

function isPropertyMismatched(prop: TaxonomyProperty): boolean {
  if (!fitness.value?.has_mismatched_required_attributes && !fitness.value?.blocking_mismatch) return false;
  return prop.is_required && (prop.name.toLowerCase().includes('craft') || prop.property_id === 82731);
}

function isPropertyMissingRequired(prop: TaxonomyProperty): boolean {
  if (!prop.is_required) return false;
  if (isPropertyMismatched(prop)) return false;
  const entry = localPropertiesMap.value[String(prop.property_id)];
  return !entry || !entry.values || entry.values.length === 0;
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
      const maxAllowed = prop.max_values_allowed || 5;
      if (values.length >= maxAllowed) {
        // Drop oldest to respect max_values_allowed
        values.shift();
        valueIds.shift();
      }
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

function removeSelectedValue(propId: number, valName: string) {
  const key = String(propId);
  const entry = localPropertiesMap.value[key];
  if (!entry || !entry.values) return;

  const idx = entry.values.indexOf(valName);
  if (idx >= 0) {
    const nextVals = [...entry.values];
    nextVals.splice(idx, 1);
    const nextIds = entry.value_ids ? [...entry.value_ids] : [];
    if (nextIds.length > idx) nextIds.splice(idx, 1);

    if (nextVals.length === 0) {
      delete localPropertiesMap.value[key];
    } else {
      localPropertiesMap.value[key] = {
        ...entry,
        values: nextVals,
        value_ids: nextIds,
      };
    }
    emit('update:etsyProperties', { ...localPropertiesMap.value });
  }
}

function onDropdownSelect(prop: TaxonomyProperty, event: Event) {
  const target = event.target as HTMLSelectElement;
  const valName = target.value;
  if (!valName) {
    delete localPropertiesMap.value[String(prop.property_id)];
    emit('update:etsyProperties', { ...localPropertiesMap.value });
    return;
  }

  const matchVal = prop.possible_values?.find((v) => v.name === valName);
  const valId = matchVal?.value_id;

  localPropertiesMap.value[String(prop.property_id)] = {
    property_id: prop.property_id,
    value_ids: valId !== undefined ? [valId] : [],
    values: [valName],
  };

  emit('update:etsyProperties', { ...localPropertiesMap.value });
}

function onMeasurementValueChange(prop: TaxonomyProperty, valStr: string) {
  const key = String(prop.property_id);
  const cleanVal = valStr.trim();
  const existing = localPropertiesMap.value[key];
  const defaultScale = prop.scales?.[0];

  if (!cleanVal) {
    delete localPropertiesMap.value[key];
    emit('update:etsyProperties', { ...localPropertiesMap.value });
    return;
  }

  const scaleId = existing?.scale_id || defaultScale?.scale_id || 5; // Default Inches
  const scaleName = existing?.scale_name || defaultScale?.display_name || 'Inches';

  localPropertiesMap.value[key] = {
    property_id: prop.property_id,
    scale_id: scaleId,
    scale_name: scaleName,
    value: cleanVal,
    values: [cleanVal],
    value_ids: [],
  };

  emit('update:etsyProperties', { ...localPropertiesMap.value });
}

function onMeasurementScaleChange(prop: TaxonomyProperty, scaleIdNum: number) {
  const key = String(prop.property_id);
  const existing = localPropertiesMap.value[key];
  const matchedScale = prop.scales?.find((s) => s.scale_id === scaleIdNum);

  if (!existing || !existing.value) return;

  localPropertiesMap.value[key] = {
    ...existing,
    scale_id: scaleIdNum,
    scale_name: matchedScale?.display_name || '',
  };

  emit('update:etsyProperties', { ...localPropertiesMap.value });
}

function clearOptionalAttributes() {
  const requiredPropIds = new Set(
    properties.value.filter((p) => p.is_required).map((p) => String(p.property_id))
  );

  const nextMap: Record<string, any> = {};
  for (const [k, v] of Object.entries(localPropertiesMap.value)) {
    if (requiredPropIds.has(k)) {
      nextMap[k] = v;
    }
  }

  localPropertiesMap.value = nextMap;
  emit('update:etsyProperties', nextMap);
}

const isDirty = computed(() => {
  return JSON.stringify(localPropertiesMap.value) !== JSON.stringify(props.etsyProperties || {});
});

const totalSelectedCount = computed(() => {
  const eligibleIds = new Set(usableProperties.value.map((p) => String(p.property_id)));
  let count = 0;
  for (const [k, entry] of Object.entries(localPropertiesMap.value)) {
    if (!eligibleIds.has(k)) continue;
    if (entry.value) {
      count += 1;
    } else if (entry.values) {
      count += entry.values.length;
    }
  }
  return count;
});

function getFilteredComboboxValues(prop: TaxonomyProperty) {
  if (!prop.possible_values) return [];
  const query = (searchQueryMap.value[prop.property_id] || '').toLowerCase().trim();
  if (!query) {
    return prop.possible_values.slice(0, 40);
  }
  return prop.possible_values.filter((v) => v.name.toLowerCase().includes(query)).slice(0, 40);
}
</script>

<template>
  <Card class="border-border bg-card shadow-xs" data-testid="taxonomy-attributes-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div class="space-y-0.5">
        <CardTitle class="text-sm font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:sliders-horizontal" class="size-4 text-primary" aria-hidden="true" />
          <span>Category Attributes</span>
          <Badge
            :variant="totalSelectedCount > 0 ? 'success' : 'secondary'"
            class="text-[10px] font-mono font-medium"
          >
            <span v-if="totalSelectedCount > 0" class="size-1.5 rounded-full bg-emerald-500 animate-pulse mr-1" aria-hidden="true" />
            {{ totalSelectedCount }} selected
          </Badge>
          <button
            type="button"
            class="text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
            title="Category attributes info"
            @click="showInfoTooltip = !showInfoTooltip"
          >
            <Icon name="lucide:info" class="size-3.5" aria-hidden="true" />
          </button>
        </CardTitle>
        <CardDescription class="text-xs">
          Details provided by Etsy for this category. All selections are completely manual.
        </CardDescription>
      </div>

      <div class="flex items-center gap-1.5 shrink-0 flex-wrap">
        <!-- Reconcile Button -->
        <Button
          type="button"
          variant="outline"
          size="sm"
          class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer gap-1"
          title="Clean invalid or stale attributes from prior categories"
          @click="reconcileStaleAttributes"
        >
          <Icon name="lucide:refresh-cw" class="size-3 text-muted-foreground" aria-hidden="true" />
          <span>Clean Stale</span>
        </Button>

        <!-- Clear Optional -->
        <Button
          v-if="totalSelectedCount > 0"
          type="button"
          variant="ghost"
          size="sm"
          class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
          title="Clear optional attribute selections"
          @click="clearOptionalAttributes"
        >
          Clear Optional
        </Button>

        <!-- Save Button (Only when dirty) -->
        <Button
          v-if="isDirty"
          type="button"
          variant="default"
          size="sm"
          :disabled="isSaving"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save Attributes</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Info Tooltip Banner -->
      <div v-if="showInfoTooltip" class="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-foreground space-y-1">
        <p class="font-medium text-foreground">What are Category Attributes?</p>
        <p class="text-muted-foreground leading-relaxed">
          Etsy taxonomy attributes allow shoppers to filter search results by specific dimensions like Materials, Subject, Aspect Ratio, Room, Orientation, and Framing.
        </p>
      </div>

      <!-- Warning Banner for Mismatched Required Attributes -->
      <div
        v-if="fitness?.has_mismatched_required_attributes || fitness?.blocking_mismatch || (fitness?.warnings && fitness.warnings.length > 0)"
        class="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        data-testid="category-attribute-mismatch-warning"
      >
        <div class="space-y-1 min-w-0">
          <p class="font-semibold flex items-center gap-1.5 text-foreground">
            <Icon name="lucide:alert-triangle" class="size-4 shrink-0 text-amber-500" aria-hidden="true" />
            <span>Category mismatch</span>
          </p>
          <p class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed">
            {{ fitness?.mismatched_required_reason || fitness?.warnings?.[0] || 'Required Etsy attributes for this category do not match this campaign\'s intended use.' }}
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          class="h-8 text-xs shrink-0 cursor-pointer self-start sm:self-auto bg-background text-foreground border-border hover:bg-muted"
          @click="emit('reviewCategory')"
        >
          <Icon name="lucide:folder-tree" class="size-3.5 mr-1 text-primary" aria-hidden="true" />
          <span>Review Etsy Category</span>
        </Button>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="py-6 flex flex-col items-center justify-center gap-2 text-muted-foreground text-xs">
        <Icon name="lucide:loader-2" class="size-5 animate-spin text-primary" aria-hidden="true" />
        <span>Loading Etsy category properties...</span>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="usableProperties.length === 0"
        class="py-6 text-center text-xs text-muted-foreground space-y-1"
        data-testid="empty-attributes-state"
      >
        <Icon name="lucide:sliders-horizontal" class="size-6 text-muted-foreground/50 mx-auto" aria-hidden="true" />
        <p class="font-medium">No customizable attributes for this category</p>
        <p class="text-2xs text-muted-foreground">Etsy does not define specific tag attributes for this category node.</p>
      </div>

      <!-- Properties Form -->
      <div v-else class="space-y-4">
        <div
          v-for="prop in usableProperties"
          :key="prop.property_id"
          class="space-y-2 p-3.5 rounded-lg border border-border/60 bg-muted/10 transition-colors"
          :data-testid="`property-row-${prop.property_id}`"
        >
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2">
              <Label class="text-xs font-semibold text-foreground">
                {{ getPropertyDisplayName(prop) }}
              </Label>
              <Badge
                v-if="prop.is_required"
                :variant="isPropertyMissingRequired(prop) ? 'destructive' : isPropertyMismatched(prop) ? 'warning' : 'success'"
                class="text-[10px] py-0 font-medium"
              >
                * Required
              </Badge>
              <Badge v-else variant="outline" class="text-[10px] py-0 text-muted-foreground">
                Optional
              </Badge>
              <span v-if="prop.max_values_allowed && prop.is_multivalued" class="text-[11px] text-muted-foreground">
                (Max {{ prop.max_values_allowed }})
              </span>
            </div>

            <!-- Missing / Mismatch indicator -->
            <Badge
              v-if="isPropertyMismatched(prop)"
              variant="warning"
              class="text-[9px] px-1.5 py-0 gap-1 font-mono font-medium"
            >
              <Icon name="lucide:alert-triangle" class="size-2.5 text-amber-500 shrink-0" aria-hidden="true" />
              <span>Category mismatch</span>
            </Badge>
            <Badge
              v-else-if="isPropertyMissingRequired(prop)"
              variant="destructive"
              class="text-[9px] px-1.5 py-0 gap-1 font-mono font-medium"
            >
              <Icon name="lucide:alert-circle" class="size-2.5 text-red-500 shrink-0" aria-hidden="true" />
              <span>Required selection missing</span>
            </Badge>
          </div>

          <!-- TYPE 1: Measurement Scale Property (e.g. Width, Height) -->
          <div v-if="prop.scales && prop.scales.length > 0 && (!prop.possible_values || prop.possible_values.length === 0)" class="flex items-center gap-2 pt-1">
            <div class="w-32">
              <Input
                type="number"
                placeholder="e.g. 15"
                class="h-8 text-xs font-mono"
                :model-value="localPropertiesMap[String(prop.property_id)]?.value || ''"
                @update:model-value="onMeasurementValueChange(prop, String($event))"
              />
            </div>
            <select
              class="flex h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              :value="localPropertiesMap[String(prop.property_id)]?.scale_id || prop.scales[0]?.scale_id || 5"
              @change="onMeasurementScaleChange(prop, Number(($event.target as HTMLSelectElement).value))"
            >
              <option v-for="scale in prop.scales" :key="scale.scale_id" :value="scale.scale_id">
                {{ scale.display_name }}
              </option>
            </select>
          </div>

          <!-- TYPE 2: Large Multi-valued Property with Searchable Combobox (e.g. Materials with 500+ choices) -->
          <div v-else-if="prop.is_multivalued && prop.possible_values && prop.possible_values.length > 25" class="space-y-2 pt-1">
            <!-- Selected Pills -->
            <div v-if="localPropertiesMap[String(prop.property_id)]?.values?.length" class="flex flex-wrap gap-1.5 pb-1">
              <span
                v-for="valName in localPropertiesMap[String(prop.property_id)]?.values"
                :key="valName"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-primary text-primary-foreground shadow-2xs"
              >
                <span>{{ valName }}</span>
                <button
                  type="button"
                  class="cursor-pointer hover:text-white/80 transition-colors"
                  :title="`Remove ${valName}`"
                  @click="removeSelectedValue(prop.property_id, valName)"
                >
                  <Icon name="lucide:x" class="size-3" aria-hidden="true" />
                </button>
              </span>
            </div>

            <!-- Search input -->
            <div class="relative">
              <Icon name="lucide:search" class="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground pointer-events-none" aria-hidden="true" />
              <input
                type="text"
                :placeholder="`Search ${getPropertyDisplayName(prop).toLowerCase()}...`"
                class="flex h-8 w-full rounded-md border border-input bg-background pl-8 pr-3 py-1 text-xs shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                :value="searchQueryMap[prop.property_id] || ''"
                @input="searchQueryMap[prop.property_id] = ($event.target as HTMLInputElement).value"
              />
            </div>

            <!-- Filtered Choices -->
            <div class="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1 border border-border/40 rounded-md bg-card/60">
              <button
                v-for="val in getFilteredComboboxValues(prop)"
                :key="val.value_id"
                type="button"
                class="px-2 py-1 rounded text-xs transition-colors cursor-pointer border flex items-center gap-1.5"
                :class="
                  isValueSelected(prop.property_id, val.name)
                    ? 'bg-primary text-primary-foreground border-primary font-medium'
                    : 'bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground border-border/60'
                "
                @click="toggleValue(prop, val.name, val.value_id)"
              >
                <Icon
                  v-if="isValueSelected(prop.property_id, val.name)"
                  name="lucide:check"
                  class="size-3"
                  aria-hidden="true"
                />
                <span>{{ val.name }}</span>
              </button>
            </div>
          </div>

          <!-- TYPE 3: Small Multi-valued Property (<= 25 items, e.g. Aspect ratio, Room, Subject) -->
          <div v-else-if="prop.is_multivalued && prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1.5 pt-1">
            <button
              v-for="val in prop.possible_values"
              :key="val.value_id"
              type="button"
              class="px-2.5 py-1 rounded-md text-xs transition-colors cursor-pointer border flex items-center gap-1.5"
              :class="
                isValueSelected(prop.property_id, val.name)
                  ? 'bg-primary text-primary-foreground border-primary font-medium shadow-2xs'
                  : 'bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground border-border/60'
              "
              @click="toggleValue(prop, val.name, val.value_id)"
            >
              <Icon
                v-if="isValueSelected(prop.property_id, val.name)"
                name="lucide:check"
                class="size-3"
                aria-hidden="true"
              />
              <span>{{ val.name }}</span>
            </button>
          </div>

          <!-- TYPE 4: Single-valued Property (<= 6 items): Radio/Pill Chips -->
          <div
            v-else-if="!prop.is_multivalued && prop.possible_values && prop.possible_values.length <= 6 && prop.possible_values.length > 0"
            class="flex flex-wrap gap-1.5 pt-1"
          >
            <button
              v-for="val in prop.possible_values"
              :key="val.value_id"
              type="button"
              class="px-2.5 py-1 rounded-md text-xs transition-colors cursor-pointer border flex items-center gap-1.5"
              :class="
                isValueSelected(prop.property_id, val.name)
                  ? 'bg-primary text-primary-foreground border-primary font-medium shadow-2xs'
                  : 'bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground border-border/60'
              "
              @click="toggleValue(prop, val.name, val.value_id)"
            >
              <Icon
                v-if="isValueSelected(prop.property_id, val.name)"
                name="lucide:check"
                class="size-3"
                aria-hidden="true"
              />
              <span>{{ val.name }}</span>
            </button>
          </div>

          <!-- TYPE 5: Single-valued Property (> 6 items): Clean Select Dropdown -->
          <div v-else-if="prop.possible_values && prop.possible_values.length > 6" class="pt-1">
            <select
              class="flex h-8 w-full max-w-sm rounded-md border border-input bg-background px-2.5 py-1 text-xs shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              :value="localPropertiesMap[String(prop.property_id)]?.values?.[0] || ''"
              @change="onDropdownSelect(prop, $event)"
            >
              <option value="">-- Not selected --</option>
              <option v-for="val in prop.possible_values" :key="val.value_id" :value="val.name">
                {{ val.name }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

