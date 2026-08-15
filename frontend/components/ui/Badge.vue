<script setup lang="ts">
import { type HTMLAttributes, computed } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-sky-600 text-white shadow hover:bg-sky-700",
        secondary: "border-transparent bg-slate-100 text-slate-800 hover:bg-slate-200",
        destructive: "border-transparent bg-red-100 text-red-800 border border-red-200",
        outline: "text-slate-700 border border-slate-200 bg-white",
        success: "border-transparent bg-emerald-100 text-emerald-800 border border-emerald-200",
        warning: "border-transparent bg-amber-100 text-amber-900 border border-amber-200",
        info: "border-transparent bg-sky-100 text-sky-800 border border-sky-200",
        purple: "border-transparent bg-purple-100 text-purple-800 border border-purple-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export type BadgeVariants = VariantProps<typeof badgeVariants>;

interface Props {
  variant?: BadgeVariants["variant"];
  class?: HTMLAttributes["class"];
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  class: undefined,
});

const classes = computed(() => cn(badgeVariants({ variant: props.variant }), props.class));
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
