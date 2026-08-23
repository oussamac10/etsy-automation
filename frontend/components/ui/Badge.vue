<script setup lang="ts">
import { computed } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-white shadow-2xs",
        secondary: "border-border bg-secondary text-secondary-foreground",
        destructive: "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400",
        outline: "border-border text-secondary-foreground bg-card",
        success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        warning: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
        info: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
        accent: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
        purple: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
        etsy: "border-orange-500/30 bg-orange-500/10 text-orange-600 dark:text-orange-400 font-bold",
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
