<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  for?: string;
  class?: HTMLAttributes["class"];
  required?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  for: undefined,
  class: undefined,
  required: false,
});

const classes = computed(() =>
  cn("text-xs font-semibold uppercase tracking-wider text-secondary-foreground select-none", props.class)
);
</script>

<template>
  <label :for="props.for" :class="classes">
    <slot />
    <span v-if="required" class="text-destructive ml-0.5">*</span>
  </label>
</template>
