<script setup lang="ts">
import { computed } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-white shadow-2xs",
        secondary: "border-border bg-secondary text-secondary-foreground",
        destructive: "border-red-300 dark:border-red-800 bg-red-100 dark:bg-red-950/80 text-red-950 dark:text-red-200",
        outline: "border-border text-foreground bg-background",
        success: "border-emerald-300 dark:border-emerald-800 bg-emerald-100 dark:bg-emerald-950/80 text-emerald-950 dark:text-emerald-200",
        warning: "border-amber-300 dark:border-amber-700 bg-amber-100 dark:bg-amber-950/80 text-amber-950 dark:text-amber-200",
        info: "border-blue-300 dark:border-blue-800 bg-blue-100 dark:bg-blue-950/80 text-blue-950 dark:text-blue-200",
        accent: "border-violet-300 dark:border-violet-800 bg-violet-100 dark:bg-violet-950/80 text-violet-950 dark:text-violet-200",
        purple: "border-violet-300 dark:border-violet-800 bg-violet-100 dark:bg-violet-950/80 text-violet-950 dark:text-violet-200",
        etsy: "border-orange-300 dark:border-orange-700 bg-orange-100 dark:bg-orange-950/80 text-orange-950 dark:text-orange-200 font-bold",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

type BadgeProps = VariantProps<typeof badgeVariants>;

interface Props {
  variant?: BadgeProps["variant"];
  class?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  class: undefined,
});

const classes = computed(() => cn(badgeVariants({ variant: props.variant }), props.class));
</script>

<template>
  <div :class="classes">
    <slot />
  </div>
</template>
