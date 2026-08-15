<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
}>();

const classes = computed(() =>
  cn("rounded-xl border border-slate-200 bg-white text-slate-900 shadow-sm transition-all", props.class)
);
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
