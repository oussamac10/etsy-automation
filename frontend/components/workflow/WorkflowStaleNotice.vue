<script setup lang="ts">
interface Props {
  title?: string;
  reasons?: string[];
  actionLabel?: string;
  isActionLoading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: "Outdated Upstream Context",
  reasons: () => [],
  actionLabel: "",
  isActionLoading: false,
});

const emit = defineEmits<{
  (e: "action"): void;
}>();
</script>

<template>
  <div
    v-if="reasons && reasons.length > 0"
    role="alert"
    class="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 transition-all duration-200"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-start gap-3">
        <div class="mt-0.5 shrink-0">
          <Icon name="lucide:alert-triangle" class="size-4 text-amber-500" aria-hidden="true" />
        </div>
        <div class="space-y-1">
          <h4 class="text-xs font-semibold text-foreground">
            {{ title }}
          </h4>
          <ul class="space-y-1">
            <li
              v-for="(reason, idx) in reasons"
              :key="idx"
              class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed"
            >
              {{ reason }}
            </li>
          </ul>
        </div>
      </div>

      <button
        v-if="actionLabel"
        type="button"
        :disabled="isActionLoading"
        class="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-500 text-stone-950 hover:bg-amber-400 active:scale-95 transition-all disabled:opacity-50 shadow-xs"
        @click="emit('action')"
      >
        <Icon
          v-if="isActionLoading"
          name="lucide:loader-2"
          class="size-3.5 animate-spin"
          aria-hidden="true"
        />
        <Icon
          v-else
          name="lucide:refresh-cw"
          class="size-3.5"
          aria-hidden="true"
        />
        <span>{{ actionLabel }}</span>
      </button>
    </div>
  </div>
</template>
