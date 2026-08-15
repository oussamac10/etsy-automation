<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  value?: number;
  max?: number;
  class?: HTMLAttributes["class"];
  indicatorClass?: HTMLAttributes["class"];
}

const props = withDefaults(defineProps<Props>(), {
  value: 0,
  max: 100,
  class: undefined,
  indicatorClass: undefined,
});

const percentage = computed(() => {
  const clamped = Math.min(Math.max(props.value || 0, 0), props.max);
  return (clamped / props.max) * 100;
});

const rootClasses = computed(() =>
  cn("relative h-2 w-full overflow-hidden rounded-full bg-slate-100", props.class)
);

const indicatorClasses = computed(() =>
  cn("h-full w-full flex-1 bg-sky-600 transition-all duration-300 ease-in-out", props.indicatorClass)
);
</script>

<template>
  <div :class="rootClasses" role="progressbar" :aria-valuenow="value" :aria-valuemin="0" :aria-valuemax="max">
    <div :class="indicatorClasses" :style="{ transform: `translateX(-${100 - percentage}%)` }" />
  </div>
</template>
