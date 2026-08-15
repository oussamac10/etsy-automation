<script setup lang="ts">
import { computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  modelValue?: string | number | null;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  id?: string;
  class?: string;
  error?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: "",
  type: "text",
  placeholder: undefined,
  disabled: false,
  required: false,
  id: undefined,
  class: undefined,
  error: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number): void;
}>();

const classes = computed(() =>
  cn(
    "flex h-9 w-full rounded-lg border border-zinc-200 bg-white px-3 py-1 text-sm shadow-2xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 focus-visible:border-indigo-500 disabled:cursor-not-allowed disabled:opacity-50",
    props.error && "border-rose-500 focus-visible:ring-rose-500",
    props.class
  )
);

function onInput(event: Event) {
  const target = event.target as HTMLInputElement;
  emit("update:modelValue", target.value);
}
</script>

<template>
  <input
    :id="id"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :required="required"
    :class="classes"
    @input="onInput"
  >
</template>
