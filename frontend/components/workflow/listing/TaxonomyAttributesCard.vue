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
const showOtherProperties = ref(false);

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
  () => [props.workflowId, props.taxonomyId],
  () => {
    loadTaxonomyProperties();
    loadFitness();
  }
);

// Only keep properties that have possible values or are required
const usableProperties = computed(() => {
  return properties.value.filter((p) => p.is_required || (p.possible_values && p.possible_values.length > 0));
});

const RECOMMENDED_PROP_KEYWORDS = ['craft', 'primary color', 'secondary color', 'holiday', 'occasion', 'style', 'season'];

const recommendedProperties = computed(() => {
  return usableProperties.value.filter((p) => {
    if (p.is_required) return true;
    const nameLower = p.name.toLowerCase();
    return RECOMMENDED_PROP_KEYWORDS.some((kw) => nameLower.includes(kw));
  });
});

const otherProperties = computed(() => {
  const recIds = new Set(recommendedProperties.value.map((p) => p.property_id));
  return usableProperties.value.filter((p) => !recIds.has(p.property_id));
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

onMounted(() => {
  loadTaxonomyProperties();
  loadFitness();
});

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
  return Object.values(localPropertiesMap.value).reduce((acc, curr) => acc + (curr.values?.length || 0), 0);
});
</script>

<template>
  <Card class="border-border bg-card shadow-xs" data-testid="taxonomy-attributes-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div class="space-y-0.5">
        <CardTitle class="text-sm font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:sliders-horizontal" class="size-4 text-primary" aria-hidden="true" />
          <span>Category Attributes</span>
          <Badge variant="outline" class="text-[10px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20">
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
          Optional and required details provided by Etsy for the selected category.
        </CardDescription>
      </div>

      <div class="flex items-center gap-1.5 shrink-0 flex-wrap">
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
          <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Info Alert Box -->
      <div v-if="showInfoTooltip" class="p-3 rounded-lg border border-border bg-muted/30 text-xs space-y-1.5">
        <p class="font-medium text-foreground">About Etsy Category Attributes</p>
        <p class="text-muted-foreground text-[11px] leading-relaxed">
          These attributes come directly from Etsy's seller taxonomy. Selecting accurate properties helps Etsy buyers find your digital download. Values are 100% manual and draft-only.
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
        class="py-6 text-center text-xs text-muted-foreground border border-dashed rounded-lg"
      >
        <Icon name="lucide:check-circle" class="size-5 text-emerald-600 mx-auto mb-1.5" aria-hidden="true" />
        <p>No additional attributes required by Etsy for this category.</p>
      </div>

      <!-- Properties Form -->
      <div v-else class="space-y-4">
        <!-- Recommended / Core Properties -->
        <div
          v-for="prop in recommendedProperties"
          :key="prop.property_id"
          class="p-3.5 rounded-lg border border-border/80 bg-card/60 space-y-2.5 transition-colors"
          :class="{
            'border-amber-500/30 bg-amber-500/5': isPropertyMismatched(prop),
            'border-destructive/30 bg-destructive/5': isPropertyMissingRequired(prop),
          }"
        >
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2">
              <Label class="text-xs font-semibold text-foreground">
                {{ prop.name }}
              </Label>
              <Badge
                v-if="prop.is_required"
                variant="outline"
                class="text-[10px] py-0 font-medium text-foreground"
                :class="
                  isPropertyMismatched(prop)
                    ? 'bg-amber-500/10 border-amber-500/30'
                    : isPropertyMissingRequired(prop)
                    ? 'bg-destructive/10 text-destructive border-destructive/20'
                    : 'bg-emerald-500/10 border-emerald-500/20'
                "
              >
                * Required
              </Badge>
              <Badge v-else variant="outline" class="text-[10px] py-0 text-muted-foreground">
                Optional
              </Badge>
            </div>

            <!-- Missing / Mismatch indicator -->
            <span v-if="isPropertyMismatched(prop)" class="text-[11px] font-medium text-amber-600 dark:text-amber-400">
              Category mismatch
            </span>
            <span v-else-if="isPropertyMissingRequired(prop)" class="text-[11px] font-medium text-destructive">
              Required selection missing
            </span>
          </div>

          <!-- Multi-valued Property: Tag Chips -->
          <div v-if="prop.is_multivalued && prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1.5 pt-1">
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

          <!-- Single-valued Property (<= 6 items): Radio/Toggle Chips -->
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

          <!-- Single-valued Property (> 6 items): Dropdown with '-- Not selected --' -->
          <div v-else-if="prop.possible_values && prop.possible_values.length > 6" class="pt-1">
            <select
              class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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

        <!-- Other / Secondary Properties Collapsible -->
        <div v-if="otherProperties.length > 0" class="pt-2 border-t border-border/50">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="w-full justify-between text-xs text-muted-foreground hover:text-foreground h-8"
            @click="showOtherProperties = !showOtherProperties"
          >
            <span>Other Etsy Attributes ({{ otherProperties.length }})</span>
            <Icon
              :name="showOtherProperties ? 'lucide:chevron-up' : 'lucide:chevron-down'"
              class="size-3.5"
              aria-hidden="true"
            />
          </Button>

          <div v-if="showOtherProperties" class="space-y-3 pt-3">
            <div
              v-for="prop in otherProperties"
              :key="prop.property_id"
              class="p-3 rounded-lg border border-border bg-card/40 space-y-2"
            >
              <div class="flex items-center justify-between gap-2">
                <Label class="text-xs font-semibold text-foreground">
                  {{ prop.name }}
                </Label>
                <Badge variant="outline" class="text-[10px] py-0 text-muted-foreground">
                  Optional
                </Badge>
              </div>

              <!-- Multivalued chips -->
              <div v-if="prop.is_multivalued && prop.possible_values && prop.possible_values.length > 0" class="flex flex-wrap gap-1.5 pt-1">
                <button
                  v-for="val in prop.possible_values"
                  :key="val.value_id"
                  type="button"
                  class="px-2 py-0.5 rounded text-xs transition-colors cursor-pointer border"
                  :class="
                    isValueSelected(prop.property_id, val.name)
                      ? 'bg-primary text-primary-foreground border-primary font-medium'
                      : 'bg-muted/40 hover:bg-muted text-muted-foreground border-border/60'
                  "
                  @click="toggleValue(prop, val.name, val.value_id)"
                >
                  {{ val.name }}
                </button>
              </div>

              <!-- Dropdown for others -->
              <div v-else-if="prop.possible_values && prop.possible_values.length > 0" class="pt-1">
                <select
                  class="flex h-8 w-full rounded-md border border-input bg-background px-2.5 py-1 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
        </div>
      </div>
    </CardContent>
  </Card>
</template>
