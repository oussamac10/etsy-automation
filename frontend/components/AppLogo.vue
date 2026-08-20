<script setup lang="ts">
withDefaults(
  defineProps<{
    sizeClass?: string;
  }>(),
  {
    sizeClass: "size-7 sm:size-8",
  }
);
</script>

<template>
  <svg
    :class="['shrink-0 select-none drop-shadow-2xs transition-transform duration-200 group-hover:scale-105', sizeClass]"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="logo-bg-grad" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#3B82F6" />
        <stop offset="50%" stop-color="#2563EB" />
        <stop offset="100%" stop-color="#1D4ED8" />
      </linearGradient>
      <linearGradient id="logo-sparkle-grad" x1="20" y1="4" x2="28" y2="12" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#FDE047" />
        <stop offset="100%" stop-color="#F59E0B" />
      </linearGradient>
      <filter id="logo-shadow" x="0" y="0" width="32" height="32" filterUnits="userSpaceOnUse">
        <feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#0F172A" flood-opacity="0.18" />
      </filter>
    </defs>

    <!-- Base Squircle Container -->
    <rect x="2" y="2" width="28" height="28" rx="7" fill="url(#logo-bg-grad)" filter="url(#logo-shadow)" />
    <rect x="2.5" y="2.5" width="27" height="27" rx="6.5" stroke="#60A5FA" stroke-opacity="0.4" stroke-width="1" />

    <!-- Marketplace Storefront / Studio Icon -->
    <!-- Awning Top -->
    <path d="M7 11.5L9 8h14l2 3.5v1.5c0 1.1-.9 2-2 2s-2-.9-2-2c0 1.1-.9 2-2 2s-2-.9-2-2c0 1.1-.9 2-2 2s-2-.9-2-2c0 1.1-.9 2-2 2s-2-.9-2-2v-1.5z" fill="#FFFFFF" fill-opacity="0.95" />
    
    <!-- Store Body -->
    <path d="M8 15v8c0 .55.45 1 1 1h14c.55 0 1-.45 1-1v-8" stroke="#FFFFFF" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
    
    <!-- Store Door / Counter -->
    <path d="M13 24v-5c0-.55.45-1 1-1h4c.55 0 1 .45 1 1v5" fill="#DBEAFE" fill-opacity="0.3" stroke="#FFFFFF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />

    <!-- Magic Sparkle (Automation / AI indicator) -->
    <path d="M24 4.5L24.8 6.8L27 7.5L24.8 8.2L24 10.5L23.2 8.2L21 7.5L23.2 6.8L24 4.5Z" fill="url(#logo-sparkle-grad)" />
  </svg>
</template>
