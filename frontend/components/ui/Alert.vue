<script setup lang="ts">
import { computed } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-xl border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground text-sm",
  {
    variants: {
      variant: {
        default: "bg-white text-zinc-900 border-zinc-200",
        destructive: "border-rose-200 bg-rose-50/80 text-rose-900 [&>svg]:text-rose-600",
        warning: "border-amber-200 bg-amber-50/80 text-amber-900 [&>svg]:text-amber-600",
        info: "border-indigo-200 bg-indigo-50/80 text-indigo-900 [&>svg]:text-indigo-600",
        success: "border-emerald-200 bg-emerald-50/80 text-emerald-900 [&>svg]:text-emerald-600",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

type AlertProps = VariantProps<typeof alertVariants>;

interface Props {
  variant?: AlertProps["variant"];
  class?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  class: undefined,
});

const classes = computed(() => cn(alertVariants({ variant: props.variant }), props.class));
</script>

<template>
  <div role="alert" :class="classes">
    <slot />
  </div>
</template>
