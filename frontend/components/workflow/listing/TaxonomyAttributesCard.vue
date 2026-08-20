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
  () => props.workflowId,
  () => {
    loadTaxonomyProperties();
  }
);

watch(
  () => props.taxonomyId,
  () => {
    loadTaxonomyProperties();
  }
);

// Only keep properties that have possible values or are required
const usableProperties = computed(() => {
  return properties.value.filter((p) => p.is_required || (p.possible_values && p.possible_values.length > 0));
});

const RECOMMENDED_PROP_KEYWORDS = ['craft', 'holiday', 'season', 'style', 'primary color', 'secondary color', 'occasion'];

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

onMounted(() => {
  loadTaxonomyProperties();
});

function isValueSelected(propId: number, valName: string): boolean {
  const entry = localPropertiesMap.value[String(propId)];
  if (!entry || !entry.values) return false;
  return entry.values.includes(valName);
}

function isPropertyMissingRequired(prop: TaxonomyProperty): boolean {
  if (!prop.is_required) return false;
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
          class="h-8 px-3 gap-1.5 text-xs font-medium shrink-0 cursor-pointer shadow-xs"
          @click="emit('save')"
        >
          <Icon v-if="isSaving" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:save" class="size-3.5" aria-hidden="true" />
          <span>Save</span>
        </Button>
      </div>

      <!-- Info Banner Tooltip -->
      <div v-if="showInfoTooltip" class="mt-2.5 p-3 rounded-lg bg-muted/60 border border-border text-xs text-muted-foreground space-y-1">
        <p class="font-semibold text-foreground flex items-center gap-1.5">
          <Icon name="lucide:info" class="size-3.5 text-primary" aria-hidden="true" />
          <span>About Category Attributes</span>
        </p>
        <p class="leading-normal">
          These attributes come directly from Etsy. Select only the values that accurately describe this listing.
        </p>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-4">
      <!-- Loading State Skeleton -->
      <div v-if="isLoading" class="space-y-3">
        <div class="h-10 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-lg" />
        <div class="h-10 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-lg" />
      </div>

      <!-- Compact Attributes 2-Column Grid Layout -->
      <div v-else-if="usableProperties.length > 0" class="space-y-4">
        <!-- Recommended Category Attributes Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="prop in recommendedProperties"
            :key="prop.property_id"
            class="p-3 rounded-lg bg-muted/30 border border-border/70 space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <Label class="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <span>{{ prop.name }}</span>
                <span v-if="prop.is_required" class="text-destructive font-bold" title="Required by Etsy">* Required</span>
                <span v-else class="text-[10px] text-muted-foreground font-normal">Optional</span>
              </Label>
              <Badge
                v-if="prop.is_multivalued"
                variant="outline"
                class="text-[9px] font-mono text-muted-foreground px-1.5 py-0"
              >
                multi
              </Badge>
            </div>

            <!-- Missing Required Warning -->
            <p v-if="isPropertyMissingRequired(prop)" class="text-[11px] text-amber-600 dark:text-amber-400 font-medium">
              Required selection missing
            </p>

            <!-- Multivalued OR Small choices <= 6: Chips -->
            <div v-if="prop.is_multivalued || (prop.possible_values && prop.possible_values.length <= 6)" class="flex flex-wrap gap-1.5">
              <button
                v-for="val in prop.possible_values"
                :key="val.value_id || val.name"
                type="button"
                class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border transition-colors cursor-pointer"
                :class="
                  isValueSelected(prop.property_id, val.name)
                    ? 'bg-primary/10 text-primary border-primary/40 font-semibold'
                    : 'bg-background text-muted-foreground border-border hover:bg-muted'
                "
                @click="toggleValue(prop, val.name, val.value_id)"
              >
                <Icon
                  :name="isValueSelected(prop.property_id, val.name) ? 'lucide:check' : 'lucide:plus'"
                  class="size-3"
                  aria-hidden="true"
                />
                <span>{{ val.name }}</span>
              </button>
            </div>

            <!-- Single-valued with > 6 choices: Dropdown -->
            <div v-else-if="prop.possible_values && prop.possible_values.length > 6" class="relative">
              <select
                class="w-full h-8 px-2.5 text-xs rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                :value="localPropertiesMap[String(prop.property_id)]?.values?.[0] || ''"
                @change="onDropdownSelect(prop, $event)"
              >
                <option value="">-- Not selected --</option>
                <option
                  v-for="val in prop.possible_values"
                  :key="val.value_id || val.name"
                  :value="val.name"
                >
                  {{ val.name }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- Collapsible Other Etsy Attributes Section -->
        <div v-if="otherProperties.length > 0" class="pt-2 border-t border-border/50 space-y-3">
          <button
            type="button"
            class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            @click="showOtherProperties = !showOtherProperties"
          >
            <Icon
              :name="showOtherProperties ? 'lucide:chevron-down' : 'lucide:chevron-right'"
              class="size-3.5"
              aria-hidden="true"
            />
            <span>Other Etsy Attributes ({{ otherProperties.length }} additional)</span>
          </button>

          <div v-if="showOtherProperties" class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            <div
              v-for="prop in otherProperties"
              :key="prop.property_id"
              class="p-3 rounded-lg bg-muted/20 border border-border/50 space-y-2"
            >
              <div class="flex items-center justify-between gap-2">
                <Label class="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <span>{{ prop.name }}</span>
                  <span v-if="prop.is_required" class="text-destructive font-bold" title="Required by Etsy">* Required</span>
                  <span v-else class="text-[10px] text-muted-foreground font-normal">Optional</span>
                </Label>
              </div>

              <!-- Multivalued OR Small choices <= 6: Chips -->
              <div v-if="prop.is_multivalued || (prop.possible_values && prop.possible_values.length <= 6)" class="flex flex-wrap gap-1.5">
                <button
                  v-for="val in prop.possible_values"
                  :key="val.value_id || val.name"
                  type="button"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border transition-colors cursor-pointer"
                  :class="
                    isValueSelected(prop.property_id, val.name)
                      ? 'bg-primary/10 text-primary border-primary/40 font-semibold'
                      : 'bg-background text-muted-foreground border-border hover:bg-muted'
                  "
                  @click="toggleValue(prop, val.name, val.value_id)"
                >
                  <Icon
                    :name="isValueSelected(prop.property_id, val.name) ? 'lucide:check' : 'lucide:plus'"
                    class="size-3"
                    aria-hidden="true"
                  />
                  <span>{{ val.name }}</span>
                </button>
              </div>

              <!-- Single-valued with > 6 choices: Dropdown -->
              <div v-else-if="prop.possible_values && prop.possible_values.length > 6">
                <select
                  class="w-full h-8 px-2.5 text-xs rounded-md border border-border bg-background text-foreground focus:outline-none cursor-pointer"
                  :value="localPropertiesMap[String(prop.property_id)]?.values?.[0] || ''"
                  @change="onDropdownSelect(prop, $event)"
                >
                  <option value="">-- Not selected --</option>
                  <option
                    v-for="val in prop.possible_values"
                    :key="val.value_id || val.name"
                    :value="val.name"
                  >
                    {{ val.name }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty Fallback -->
      <div v-else class="text-center py-4 px-3 bg-muted/40 border border-dashed border-border rounded-lg space-y-1">
        <p class="text-xs font-semibold text-foreground">Category Attributes</p>
        <p class="text-[11px] text-muted-foreground">
          Select an Etsy category above to view available attributes.
        </p>
      </div>
    </CardContent>
  </Card>
</template>
