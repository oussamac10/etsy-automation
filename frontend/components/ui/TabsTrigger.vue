<script setup lang="ts">
import { inject, computed, type HTMLAttributes } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  value: string;
  disabled?: boolean;
  class?: HTMLAttributes["class"];
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  class: undefined,
});

const tabsState = inject<{
  currentTab: { value: string };
  setTab: (tab: string) => void;
}>("tabsState");

const isActive = computed(() => tabsState?.currentTab.value === props.value);

const classes = computed(() =>
  cn(
    "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer",
    isActive.value ? "bg-card text-foreground shadow-2xs font-bold border border-border/80" : "text-secondary-foreground hover:text-foreground hover:bg-card/60",
    props.class
  )
);

function select() {
  if (!props.disabled && tabsState) {
    tabsState.setTab(props.value);
  }
}
</script>

<template>
  <button
    type="button"
    role="tab"
    :aria-selected="isActive"
    :disabled="disabled"
    :class="classes"
    @click="select"
  >
    <slot />
  </button>
</template>
