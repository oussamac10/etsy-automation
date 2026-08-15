<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
}>();

const classes = computed(() =>
  cn("rounded-xl border border-zinc-200 bg-white text-zinc-900 shadow-2xs transition-all", props.class)
);
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
