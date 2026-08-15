<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cn } from "~/lib/utils";

interface Props {
  modelValue?: string | number | null;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  rows?: number;
  id?: string;
  class?: HTMLAttributes["class"];
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: "",
  placeholder: "",
  disabled: false,
  required: false,
  rows: 3,
  id: undefined,
  class: undefined,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const classes = computed(() =>
  cn(
    "flex min-h-[80px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50",
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
