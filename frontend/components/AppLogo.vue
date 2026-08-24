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
    :class="['shrink-0 select-none drop-shadow-xs transition-transform duration-300 group-hover:scale-105', sizeClass]"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="ncp-logo-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#FB923C" />
        <stop offset="50%" stop-color="#EA580C" />
        <stop offset="100%" stop-color="#C2410C" />
      </linearGradient>
      <linearGradient id="ncp-logo-rim" x1="2" y1="2" x2="30" y2="18" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.45" />
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.05" />
      </linearGradient>
      <radialGradient id="ncp-logo-glow" cx="16" cy="16" r="12" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#FEF08A" stop-opacity="0.5" />
        <stop offset="70%" stop-color="#F97316" stop-opacity="0" />
      </radialGradient>
      <filter id="ncp-logo-shadow" x="0" y="0" width="32" height="32" filterUnits="userSpaceOnUse">
        <feDropShadow dx="0" dy="1.5" stdDeviation="1.2" flood-color="#7C2D12" flood-opacity="0.3" />
      </filter>
    </defs>

    <!-- Base Squircle Container -->
    <rect x="2" y="2" width="28" height="28" rx="7.5" fill="url(#ncp-logo-bg)" filter="url(#ncp-logo-shadow)" />
    <rect x="2.5" y="2.5" width="27" height="27" rx="7" stroke="url(#ncp-logo-rim)" stroke-width="1" />

    <!-- Ambient Core Glow -->
    <circle cx="16" cy="16" r="10" fill="url(#ncp-logo-glow)" />

    <!-- Geometric Craft Diamond Base -->
    <path
      d="M16 6.5L25 15.5L16 24.5L7 15.5L16 6.5Z"
      fill="#FFFFFF"
      fill-opacity="0.14"
      stroke="#FFFFFF"
      stroke-opacity="0.35"
      stroke-width="0.8"
    />

    <!-- Left Prism Fold -->
    <path
      d="M16 7.5L9 14.5V17.5L16 24.5V7.5Z"
      fill="#FFFFFF"
      fill-opacity="0.22"
    />

    <!-- Right Prism Fold -->
    <path
      d="M16 7.5L23 14.5V17.5L16 24.5V7.5Z"
      fill="#FFFFFF"
      fill-opacity="0.35"
    />

    <!-- 4-Point Radiant Nova Star -->
    <path
      d="M16 9.5L17.4 13.8C17.7 14.7 18.3 15.3 19.2 15.6L23.5 17L19.2 18.4C18.3 18.7 17.7 19.3 17.4 20.2L16 24.5L14.6 20.2C14.3 19.3 13.7 18.7 12.8 18.4L8.5 17L12.8 15.6C13.7 15.3 14.3 14.7 14.6 13.8L16 9.5Z"
      fill="#FFFFFF"
    />

    <!-- Golden Nexus Center -->
    <circle cx="16" cy="17" r="1.4" fill="#FDE047" />

    <!-- Vector Pixel Nodes -->
    <rect x="22.5" y="8" width="1.5" height="1.5" rx="0.4" fill="#FFFFFF" fill-opacity="0.9" />
    <rect x="8" y="22.5" width="1.5" height="1.5" rx="0.4" fill="#FFFFFF" fill-opacity="0.6" />
  </svg>
</template>
