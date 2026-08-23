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
    "flex h-9 w-full rounded-lg border border-border bg-card px-3 py-1 text-sm text-foreground shadow-2xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50",
    props.error && "border-destructive focus-visible:ring-destructive focus-visible:border-destructive",
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
