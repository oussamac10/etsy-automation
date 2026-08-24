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
    :class="['shrink-0 select-none transition-transform duration-300 group-hover:scale-105', sizeClass]"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <!-- Left Column: Primary Pillar & Base Pixel Node -->
    <rect x="3" y="3" width="7" height="16" rx="3.5" class="fill-[#FF6B35] dark:fill-[#FF6B35]" />
    <rect x="3" y="22" width="7" height="7" rx="2.5" class="fill-[#18181B] dark:fill-[#FFB089]" />

    <!-- Center Diagonal Step: Modular Assembling Craft Pixels -->
    <rect x="12.5" y="7.5" width="7" height="7" rx="2.5" class="fill-[#FFB089] dark:fill-[#FFB089]" />
    <rect x="12.5" y="17.5" width="7" height="7" rx="2.5" class="fill-[#FF6B35] dark:fill-[#FF6B35]" />

    <!-- Right Column: Top Accent Node & Elevated Pillar -->
    <rect x="22" y="3" width="7" height="7" rx="2.5" class="fill-[#FFB089] dark:fill-[#FFB089]" />
    <rect x="22" y="13" width="7" height="16" rx="3.5" class="fill-[#FF6B35] dark:fill-[#FF6B35]" />
  </svg>
</template>
