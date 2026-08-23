<script setup lang="ts">
import { computed, useSlots } from "vue";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/lib/utils";
import Button from "~/components/ui/Button.vue";

const alertVariants = cva(
  "relative w-full rounded-xl border p-4 text-sm shadow-2xs transition-all duration-150",
  {
    variants: {
      variant: {
        default: "bg-card text-foreground border-border",
        destructive: "border-red-500/30 bg-red-500/10 text-foreground",
        warning: "border-amber-500/30 bg-amber-500/10 text-foreground",
        info: "border-blue-500/30 bg-blue-500/10 text-foreground",
        success: "border-emerald-500/30 bg-emerald-500/10 text-foreground",
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
  title?: string | null;
  description?: string | null;
  icon?: string | null;
  dismissible?: boolean;
  actionLabel?: string | null;
  actionLoading?: boolean;
  class?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  title: undefined,
  description: undefined,
  icon: undefined,
  dismissible: false,
  actionLabel: undefined,
  actionLoading: false,
  class: undefined,
});

const emit = defineEmits<{
  (e: "dismiss"): void;
  (e: "action"): void;
}>();

const slots = useSlots();

const resolvedIcon = computed(() => {
  if (props.icon) return props.icon;
  switch (props.variant) {
    case "destructive":
      return "lucide:circle-alert";
    case "warning":
      return "lucide:triangle-alert";
    case "info":
      return "lucide:info";
    case "success":
      return "lucide:circle-check";
    default:
      return "lucide:info";
  }
});

const iconColorClass = computed(() => {
  switch (props.variant) {
    case "destructive":
      return "text-red-600 dark:text-red-400";
    case "warning":
      return "text-amber-600 dark:text-amber-400";
    case "info":
      return "text-blue-600 dark:text-blue-400";
    case "success":
      return "text-emerald-600 dark:text-emerald-400";
    default:
      return "text-foreground";
  }
});

const dismissButtonHoverClass = computed(() => {
  switch (props.variant) {
    case "destructive":
      return "text-red-600 dark:text-red-400 hover:text-red-700 hover:bg-red-500/20";
    case "warning":
      return "text-amber-600 dark:text-amber-400 hover:text-amber-700 hover:bg-amber-500/20";
    case "info":
      return "text-blue-600 dark:text-blue-400 hover:text-blue-700 hover:bg-blue-500/20";
    case "success":
      return "text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 hover:bg-emerald-500/20";
    default:
      return "text-muted-foreground hover:text-foreground hover:bg-muted";
  }
});

const isPropsMode = computed(() => Boolean(props.title || props.description || props.dismissible || props.actionLabel || slots.title || slots.description));
const classes = computed(() => cn(alertVariants({ variant: props.variant }), props.class));
</script>

<template>
  <div role="alert" :class="classes">
    <!-- Declarative Props Mode -->
    <div v-if="isPropsMode" class="flex items-start gap-3">
      <div class="shrink-0 mt-0.5">
        <slot name="icon">
          <Icon :name="resolvedIcon" :class="cn('size-4', iconColorClass)" aria-hidden="true" />
        </slot>
      </div>

      <div class="flex-1 min-w-0">
        <h5 v-if="title || $slots.title" class="mb-1 font-semibold leading-tight tracking-tight">
          <slot name="title">{{ title }}</slot>
        </h5>
        <div v-if="description || $slots.description" class="text-sm leading-relaxed">
          <slot name="description">{{ description }}</slot>
        </div>
        <slot />
      </div>

      <div v-if="actionLabel || dismissible || $slots.action" class="shrink-0 flex items-center gap-2 -mr-1 -mt-1">
        <slot name="action">
          <Button
            v-if="actionLabel"
            variant="outline"
            size="sm"
            class="h-7 text-xs cursor-pointer"
            :disabled="actionLoading"
            @click="emit('action')"
          >
            <Icon v-if="actionLoading" name="lucide:loader-circle" class="size-3 animate-spin mr-1" aria-hidden="true" />
            <span>{{ actionLabel }}</span>
          </Button>
        </slot>

        <button
          v-if="dismissible"
          type="button"
          :class="cn('p-1 cursor-pointer rounded-lg transition-colors', dismissButtonHoverClass)"
          aria-label="Dismiss alert"
          @click="emit('dismiss')"
        >
          <Icon name="lucide:x" class="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>

    <!-- Fallback Slot Mode (Backwards Compatibility) -->
    <template v-else>
      <slot />
    </template>
  </div>
</template>
