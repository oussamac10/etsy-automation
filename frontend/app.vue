<script setup lang="ts">
// Root shell. Pages provide their own headings and landmarks.
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:rounded-lg focus:bg-white focus:p-2 focus:border focus:border-border focus:shadow-md focus:text-primary-hover focus:font-semibold z-50"
    >
      Skip to main content
    </a>
    <NuxtPage />
  </div>
</template>
