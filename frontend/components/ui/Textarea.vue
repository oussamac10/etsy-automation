<script setup lang="ts">
import { computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  modelValue?: string | number | null;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  rows?: number;
  id?: string;
  class?: string;
  error?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: "",
  placeholder: undefined,
  disabled: false,
  required: false,
  rows: 3,
  id: undefined,
  class: undefined,
  error: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number): void;
}>();

const classes = computed(() =>
  cn(
    "flex min-h-[80px] w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm shadow-2xs placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 focus-visible:border-indigo-500 disabled:cursor-not-allowed disabled:opacity-50",
    props.error && "border-rose-500 focus-visible:ring-rose-500",
    props.class
  )
);

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  emit("update:modelValue", target.value);
}
</script>

<template>
  <textarea
    :id="id"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :required="required"
    :rows="rows"
    :class="classes"
    @input="onInput"
  />
</template>
