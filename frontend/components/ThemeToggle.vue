<script setup lang="ts">
import { useTheme } from "~/composables/useTheme";

const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <button
    type="button"
    class="relative inline-flex size-8 items-center justify-center rounded-lg border border-border bg-secondary/60 text-secondary-foreground hover:bg-secondary hover:text-foreground transition-all duration-150 shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 cursor-pointer"
    :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
    :title="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
    data-testid="theme-toggle-btn"
    @click="toggleTheme"
  >
    <Icon
      v-if="isDark"
      name="lucide:moon"
      class="size-4 text-primary transition-transform duration-200"
      aria-hidden="true"
    />
    <Icon
      v-else
      name="lucide:sun"
      class="size-4 text-amber-500 transition-transform duration-200"
      aria-hidden="true"
    />
  </button>
</template>
