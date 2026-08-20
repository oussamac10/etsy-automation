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
        secondary: "border border-slate-200/80 dark:border-slate-700/80 bg-slate-100/80 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 shadow-2xs",
        destructive: "border border-red-200/60 dark:border-red-800/60 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 shadow-2xs",
        outline: "border border-border text-foreground bg-white dark:bg-card shadow-2xs",
        success: "border border-emerald-200/60 dark:border-emerald-800/60 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 shadow-2xs",
        warning: "border border-amber-200/60 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 shadow-2xs",
        info: "border border-blue-200/60 dark:border-blue-800/60 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 shadow-2xs",
        accent: "border border-violet-200/60 dark:border-violet-800/60 bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300 shadow-2xs",
        purple: "border border-purple-200/60 dark:border-purple-800/60 bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 shadow-2xs",
        etsy: "border border-orange-200/60 dark:border-orange-800/60 bg-orange-50 dark:bg-orange-950/40 text-[#F1641E] font-bold shadow-2xs",
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
