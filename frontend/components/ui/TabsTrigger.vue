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
    "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer",
    isActive.value ? "bg-white text-slate-900 shadow-sm font-semibold" : "hover:text-slate-900",
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
