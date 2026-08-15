<script setup lang="ts">
import { provide, ref, watch } from "vue";

interface Props {
  modelValue?: string;
  defaultValue?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const currentTab = ref(props.modelValue || props.defaultValue || "");

watch(
  () => props.modelValue,
  (val) => {
    if (val !== undefined) {
      currentTab.value = val;
    }
  }
);

function setTab(tab: string) {
  currentTab.value = tab;
  emit("update:modelValue", tab);
}

provide("tabsState", {
  currentTab,
  setTab,
});
</script>

<template>
  <div class="w-full">
    <slot />
  </div>
</template>
