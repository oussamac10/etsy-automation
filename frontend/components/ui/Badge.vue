<script setup lang="ts">
import { computed } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground shadow-2xs",
        secondary: "border-border bg-secondary text-secondary-foreground",
        destructive: "border-red-500/20 bg-red-500/10 text-foreground dark:text-foreground",
        outline: "border-border text-foreground bg-white dark:bg-card",
        success: "border-emerald-500/20 bg-emerald-500/10 text-foreground dark:text-foreground",
        warning: "border-amber-500/20 bg-amber-500/10 text-foreground dark:text-foreground",
        info: "border-blue-500/20 bg-blue-500/10 text-foreground dark:text-foreground",
        accent: "border-violet-500/20 bg-violet-500/10 text-foreground dark:text-foreground",
        purple: "border-violet-500/20 bg-violet-500/10 text-foreground dark:text-foreground",
        etsy: "border-orange-500/20 bg-orange-500/10 text-foreground font-bold",
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
