---
name: vue-tailwind-design
description: >-
  Best practices for modern Vue 3 / Nuxt 3 frontend engineering, aesthetic UI design,
  responsive layouts, Tailwind CSS tokens, state management with Pinia, and reactive
  data fetching. Use whenever designing, improving, or building frontend pages and layouts.
---

# Vue 3 & Tailwind Modern Design System

Guidelines for building aesthetic, responsive, high-performance interfaces in Vue 3 and Nuxt 3.

---

## 1. Design Aesthetics & Visual Polish

1. **Color Palette & Contrast**:
   - Use curated semantic color tokens (`background`, `foreground`, `primary`, `muted`, `accent`, `destructive`, `card`, `border`).
   - Avoid harsh pure blacks (`#000000`) in dark mode; use rich slates/zinc tones (`zinc-900`, `zinc-950`).
2. **Typography**:
   - Clean sans-serif hierarchy (Inter, Plus Jakarta Sans, Outfit).
   - Crisp headings (`font-bold tracking-tight text-foreground`), clear captions (`text-xs text-muted-foreground`).
3. **Interactive Polish**:
   - Hover and active states on every interactive element (`hover:scale-[1.02] active:scale-[0.98] transition-transform`).
   - Smooth skeleton loaders and spinner states during async fetches.

---

## 2. Nuxt 3 & Vue 3 Composition Best Practices

1. **Script Setup & TypeScript**:
   - Always use `<script setup lang="ts">`.
   - Explicitly type all `props`, `emits`, and `computed` properties.
2. **Safe Reactive State**:
   - Use `shallowRef` for large immutable payloads (e.g. lists of heavy asset objects).
   - Use `computed` for derived filtering, sorting, or formatting.
3. **Optimistic UI Updates**:
   - Immediately reflect user actions in local state before the background network request resolves, with graceful rollback on error.
