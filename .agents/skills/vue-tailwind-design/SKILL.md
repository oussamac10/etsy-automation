---
name: vue-tailwind-design
description: >-
  Best practices for modern Vue 3 / Nuxt 3 frontend engineering, aesthetic UI design,
  responsive layouts, Tailwind CSS tokens, state management with Pinia, reactive
  data fetching, and @nuxt/icon Lucide iconography. Use whenever designing, improving, or building frontend pages and layouts.
---

# Vue 3 & Tailwind Modern Design System

Guidelines for building aesthetic, responsive, high-performance interfaces in Vue 3 and Nuxt 3.

---

## 1. Design Aesthetics & Visual Polish

1. **Color Palette, Accessibility & Strict Contrast (WCAG AAA)**:
   - Use curated semantic color tokens (`background`, `foreground`, `primary`, `muted`, `accent`, `destructive`, `card`, `border`).
   - **Zero Washed-Out Text / Background Blending**: NEVER put low-contrast same-hue text on light-tinted backgrounds (e.g. NEVER `bg-amber-500/10 text-amber-700` or `bg-emerald-500/10 text-emerald-700`). Text must be immediately legible and high-contrast.
   - **Accessible Warning / Amber Palette**:
     - Container: `bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-700/60`
     - Heading: `text-amber-950 dark:text-amber-100 font-semibold`
     - Body Text: `text-amber-900 dark:text-amber-200 leading-relaxed`
     - Warning Badges: `bg-amber-100 text-amber-950 dark:bg-amber-950/80 dark:text-amber-200 border-amber-300 dark:border-amber-700 font-semibold`
     - Action buttons inside banners: Clean high-contrast interactive elements (`bg-background text-foreground border-border hover:bg-muted` or `bg-amber-600 hover:bg-amber-700 text-white`).
   - **Accessible Success / Emerald Palette**:
     - Container: `bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-700/60`
     - Text: `text-emerald-950 dark:text-emerald-100`
     - Badges: `bg-emerald-100 text-emerald-950 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700 font-semibold`
   - Avoid harsh pure blacks (`#000000`) in dark mode; use rich slates/zinc tones (`zinc-900`, `zinc-950`).
2. **Typography**:
   - Clean sans-serif hierarchy (Inter, Plus Jakarta Sans, Outfit).
   - Crisp headings (`font-bold tracking-tight text-foreground`), clear captions (`text-xs text-muted-foreground`).
3. **Interactive Polish**:
   - Hover and active states on every interactive element (`hover:scale-[1.02] active:scale-[0.98] transition-transform cursor-pointer`).
   - Smooth skeleton loaders and spinner states during async fetches (`lucide:loader-circle animate-spin`).

---

## 2. Iconography Standards (`@nuxt/icon` + Lucide)

1. **Unified Component**: Always use `<Icon name="lucide:<name>" class="size-4" aria-hidden="true" />`.
2. **No Direct Component Imports**: Never import from `lucide-vue-next` directly; local resolution is managed by `@nuxt/icon` and `@iconify-json/lucide`.
3. **No Legacy Emojis**: Never render emoji characters in buttons, tabs, badges, or selects. Use consistent Lucide icons instead.
4. **Domain Icon Helpers**: Reference domain icon mappings from `~/config/icons` (e.g. `getProductIcon`, `getWorkflowStateIcon`).

---

## 3. Feedback & Modal Architecture

1. **Universal Alert Component (`<Alert />`)**:
   - Always use the declarative `<Alert variant="..." title="..." description="..." dismissible />` single-tag component for status messages, errors, and feedback.
   - Do NOT construct custom styled ad-hoc alert boxes (`bg-emerald-500/10 border-emerald-500/30`, etc.).
   - Support dismissible notifications by adding `dismissible` and `@dismiss="clearFeedback"`.
2. **Zero Native Popups**:
   - Never call `window.alert()`, `window.confirm()`, or `window.prompt()`.
   - Always use the accessible `<Dialog>` modal component with `<DialogHeader>`, `<DialogTitle>`, `<DialogDescription>`, and `<DialogFooter>`.

---

## 4. Nuxt 3 & Vue 3 Composition Best Practices

1. **Script Setup & TypeScript**:
   - Always use `<script setup lang="ts">`.
   - Explicitly type all `props`, `emits`, and `computed` properties.
2. **Safe Reactive State & Composables**:
   - Follow clean composable patterns (`useEtsy`, `useWorkflowControls`, `useLibraryProducts`) exposing isolated `ref` states, async actions, and standardized error parsing via `getApiErrorMessage(err)`.
   - Use `shallowRef` for large immutable payloads (e.g. lists of heavy asset objects).
   - Use `computed` for derived filtering, sorting, or formatting.
3. **Optimistic UI Updates**:
   - Immediately reflect user actions in local state before the background network request resolves, with graceful rollback on error.
