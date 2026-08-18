<script setup lang="ts">
import { computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  modelValue?: number | null;
  value?: number | null;
  max?: number;
  class?: string;
  indicatorClass?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  value: undefined,
  max: 100,
  class: undefined,
  indicatorClass: undefined,
});

const resolvedValue = computed(() => {
  if (props.modelValue !== undefined && props.modelValue !== null) {
    return Number(props.modelValue);
  }
  if (props.value !== undefined && props.value !== null) {
    return Number(props.value);
  }
  return 0;
});

const percentage = computed(() => {
  if (props.max <= 0) return 0;
  return Math.min(Math.max((resolvedValue.value / props.max) * 100, 0), 100);
});
</script>

<template>
  <div
    role="progressbar"
    :aria-valuenow="resolvedValue"
    :aria-valuemin="0"
    :aria-valuemax="max"
    :class="cn('relative h-2 w-full overflow-hidden rounded-full bg-secondary', props.class)"
  >
    <div
      :class="cn('h-full w-full flex-1 bg-primary transition-all duration-300 ease-in-out', props.indicatorClass)"
      :style="{ transform: `translateX(-${100 - percentage}%)` }"
    />
  </div>
</template>
