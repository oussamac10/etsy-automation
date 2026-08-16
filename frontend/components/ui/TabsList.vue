<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
}>();

const classes = computed(() =>
  cn("inline-flex h-10 items-center justify-center rounded-lg bg-secondary/80 border border-border p-1 text-muted-foreground", props.class)
);
</script>

<template>
  <div :class="classes" role="tablist">
    <slot />
  </div>
</template>
