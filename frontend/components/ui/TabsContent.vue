<script setup lang="ts">
import { inject, computed, type HTMLAttributes } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  value: string;
  class?: HTMLAttributes["class"];
}

const props = defineProps<Props>();

const tabsState = inject<{
  currentTab: { value: string };
}>("tabsState");

const isActive = computed(() => tabsState?.currentTab.value === props.value);

const classes = computed(() =>
  cn("mt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500", props.class)
);
</script>

<template>
  <div v-show="isActive" :class="classes" role="tabpanel">
    <slot />
  </div>
</template>
