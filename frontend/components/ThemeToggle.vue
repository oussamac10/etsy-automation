<script setup lang="ts">
import { useTheme } from "~/composables/useTheme";

const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <button
    type="button"
    class="relative inline-flex size-8 items-center justify-center rounded-lg border border-border bg-secondary/60 text-secondary-foreground hover:bg-secondary hover:text-foreground transition-all duration-150 shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 cursor-pointer overflow-hidden group"
    :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
    :title="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
    data-testid="theme-toggle-btn"
    @click="toggleTheme"
  >
    <transition name="theme-icon" mode="out-in">
      <Icon
        v-if="isDark"
        key="moon"
        name="lucide:moon"
        class="size-4 text-primary transition-transform duration-300 group-hover:rotate-12"
        aria-hidden="true"
      />
      <Icon
        v-else
        key="sun"
        name="lucide:sun"
        class="size-4 text-amber-500 transition-transform duration-300 group-hover:rotate-45"
        aria-hidden="true"
      />
    </transition>
  </button>
</template>

<style scoped>
.theme-icon-enter-active,
.theme-icon-leave-active {
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}
.theme-icon-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.6);
}
.theme-icon-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.6);
}
</style>
