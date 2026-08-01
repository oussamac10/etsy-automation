<script setup lang="ts">
// Root shell. Pages provide their own headings and landmarks.
</script>

<template>
  <div class="min-h-screen">
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:rounded focus:bg-white focus:p-2"
    >
      Skip to main content
    </a>
    <NuxtPage />
  </div>
</template>
