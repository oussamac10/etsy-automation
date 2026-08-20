---
name: shadcn-vue
description: >-
  Expert guide for implementing shadcn-vue and Radix-Vue component patterns in Nuxt 3
  and Vue 3. Covers reusable UI components (Buttons, Cards, Dialogs, Badges, Tabs,
  Tooltips, Forms, Carousels, Dropdowns), accessible primitives, Lucide icons via @nuxt/icon,
  and Tailwind CSS design tokens. Activate whenever building or refactoring frontend UI components.
---

# shadcn-vue & Accessible Component Architecture

Always build frontend components following **shadcn-vue** design principles: accessible, copy-pasteable, customizable components built on top of unstyled primitives (Radix Vue) and styled with Tailwind CSS utility classes.

---

## 1. Core Principles

1. **Accessible Primitives**: Use accessible attributes (`aria-*`, `role`, keyboard navigation, focus rings, `aria-hidden="true"` on decorative icons, `aria-label` on icon-only buttons).
2. **Variants with `class-variance-authority` (cva)** or concise Tailwind composable classes:
   - Primary, Secondary, Destructive, Outline, Ghost, Link variants.
   - Sizing scales (`sm`, `md`, `lg`, `icon`).
3. **Clean Composition**:
   - Split complex components into logical sub-components (e.g. `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`).
4. **Standard Icon System (`@nuxt/icon` + Lucide)**:
   - **Always use `@nuxt/icon` syntax**: `<Icon name="lucide:<icon-name>" class="size-4" aria-hidden="true" />`.
   - **Zero Direct Imports**: Never import icons directly from `lucide-vue-next` (to ensure bundling through local `@iconify-json/lucide` collection without runtime external fetching).
   - **Zero Emojis in UI**: Do NOT mix emoji characters in buttons, tags, badges, or selects. Use consistent Lucide icons instead.
   - **Centralized Dictionary**: Import domain icon helpers from `~/config/icons` (e.g., `getProductIcon(productType)`, `getWorkflowStateIcon(state)`).

---

## 2. Icon Sizing & Usage Standards

| Context | Icon Component Syntax | Sizing Class | Example |
| :--- | :--- | :--- | :--- |
| **Buttons** | `<Icon name="lucide:..." class="size-4" />` | `size-4` (`h-4 w-4`) | `<Icon name="lucide:plus" class="size-4 mr-1.5" />` |
| **Compact / Inline Badges** | `<Icon name="lucide:..." class="size-3" />` | `size-3` (`h-3 w-3`) | `<Icon name="lucide:circle-check" class="size-3 text-emerald-600" />` |
| **Sub-tabs & Pills** | `<Icon name="lucide:..." class="size-3.5" />` | `size-3.5` (`h-3.5 w-3.5`) | `<Icon :name="getProductIcon(p)" class="size-3.5" />` |
| **Navigation & Links** | `<Icon name="lucide:..." class="size-5" />` | `size-5` (`h-5 w-5`) | `<Icon name="lucide:layout-dashboard" class="size-5" />` |
| **Hero / Feature Cards** | `<Icon name="lucide:..." class="size-6" />` | `size-6` to `size-8` | `<Icon name="lucide:sparkles" class="size-6" />` |
| **Async Loading Spinners**| `<Icon name="lucide:loader-circle" class="size-4 animate-spin" />` | `size-4` / `size-8` | Real SVG spinner with `animate-spin` |
| **Modal Close Buttons** | `<Icon name="lucide:x" class="size-4" />` | `size-4` | Button MUST have `aria-label="Close dialog"` |

---

## 3. Standard Component Patterns

### Button (`ui/Button.vue`)

```vue
<script setup lang="ts">
interface Props {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  disabled?: boolean
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'default',
  disabled: false,
  loading: false,
})

const variantClasses = {
  default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm',
  destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm',
  outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
  secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  ghost: 'hover:bg-accent hover:text-accent-foreground',
  link: 'text-primary underline-offset-4 hover:underline',
}

const sizeClasses = {
  default: 'h-9 px-4 py-2 text-sm',
  sm: 'h-8 rounded-md px-3 text-xs',
  lg: 'h-10 rounded-md px-8 text-base',
  icon: 'h-9 w-9 p-0',
}
</script>

<template>
  <button
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center rounded-md font-medium transition-colors cursor-pointer',
      'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
      'disabled:pointer-events-none disabled:opacity-50',
      variantClasses[variant],
      sizeClasses[size]
    ]"
  >
    <Icon v-if="loading" name="lucide:loader-circle" class="size-4 animate-spin mr-1.5" aria-hidden="true" />
    <slot />
  </button>
</template>
```

### Card (`ui/Card.vue`)

```vue
<template>
  <div class="rounded-xl border bg-card text-card-foreground shadow-sm transition-all hover:shadow-md">
    <slot />
  </div>
</template>
```

### Badge (`ui/Badge.vue`)

```vue
<script setup lang="ts">
defineProps<{
  variant?: 'default' | 'secondary' | 'outline' | 'destructive' | 'success' | 'warning'
}>()
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring',
      variant === 'secondary' ? 'bg-secondary text-secondary-foreground' :
      variant === 'outline' ? 'border border-input text-foreground' :
      variant === 'destructive' ? 'bg-red-100 text-red-950 dark:bg-red-950/80 dark:text-red-200 border border-red-300 dark:border-red-700' :
      variant === 'success' ? 'bg-emerald-100 text-emerald-950 dark:bg-emerald-950/80 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700' :
      variant === 'warning' ? 'bg-amber-100 text-amber-950 dark:bg-amber-950/80 dark:text-amber-200 border border-amber-300 dark:border-amber-700' :
      'bg-primary text-primary-foreground'
    ]"
  >
    <slot />
  </span>
</template>
```

### Alert (`ui/Alert.vue`)

Universal, single-tag or slot-based accessible alert banner with automated Lucide icon resolution, typography, action buttons, and dismiss controls.

```vue
<!-- 1. Declarative Props Mode (Recommended) -->
<Alert
  variant="success"
  title="Connection Successful"
  description="Etsy shop connected successfully!"
  dismissible
  @dismiss="onDismiss"
/>

<Alert
  variant="destructive"
  title="Operation Failed"
  :description="errorMessage"
  action-label="Retry"
  :action-loading="isRetrying"
  dismissible
  @action="handleRetry"
  @dismiss="clearError"
/>

<!-- 2. Slot Mode with Custom Action Slot -->
<Alert variant="warning" title="Connection Required" description="Please connect your Etsy shop.">
  <template #action>
    <NuxtLink to="/settings">
      <Button variant="outline" size="sm" class="text-xs">Open Settings</Button>
    </NuxtLink>
  </template>
</Alert>
```

**Props:**

- `variant`: `'default' | 'destructive' | 'warning' | 'info' | 'success'` (default: `'default'`)
- `title`: `string | null`
- `description`: `string | null`
- `icon`: `string | null` (optional custom icon name; automatically defaults to variant icon)
- `dismissible`: `boolean` (renders accessible close X button)
- `actionLabel`: `string | null` (renders action button)
- `actionLoading`: `boolean` (displays spinner inside action button)

**Automatic Variant Icons:**

- `success` -> `lucide:circle-check` (emerald-600)
- `destructive` -> `lucide:circle-alert` (red-600)
- `warning` -> `lucide:triangle-alert` (amber-600)
- `info` -> `lucide:info` (blue-600)

---

### Dialog & Confirmation Modal (`ui/Dialog.vue`)

**Rule:** NEVER use browser-native `window.confirm()` or `window.alert()`. Always use accessible `<Dialog>` modals.

```vue
<Dialog :open="showModal" max-width="md" @close="showModal = false">
  <DialogHeader>
    <div class="flex items-center gap-3 text-destructive">
      <div class="h-10 w-10 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center justify-center shrink-0">
        <Icon name="lucide:unplug" class="size-5 text-destructive" aria-hidden="true" />
      </div>
      <div>
        <DialogTitle>Disconnect Shop</DialogTitle>
        <DialogDescription class="mt-1">
          Are you sure you want to disconnect <strong>{{ shopName }}</strong>?
        </DialogDescription>
      </div>
    </div>
  </DialogHeader>

  <div class="py-2 text-xs text-muted-foreground">
    <p>This action will revoke stored OAuth credentials.</p>
  </div>

  <DialogFooter class="gap-2 sm:gap-0">
    <Button variant="outline" size="sm" :disabled="isLoading" @click="showModal = false">
      Cancel
    </Button>
    <Button variant="destructive" size="sm" :disabled="isLoading" @click="confirmAction">
      <Icon v-if="isLoading" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
      <Icon v-else name="lucide:unplug" class="size-3.5" aria-hidden="true" />
      <span>{{ isLoading ? 'Processing...' : 'Disconnect' }}</span>
    </Button>
  </DialogFooter>
</Dialog>
```

---

## 4. UI Guidelines

- **Zero Native Dialogs**: Never invoke `window.alert()`, `window.confirm()`, or `window.prompt()`. Always use Radix-backed `<Dialog>` components.
- **Single-Tag Alerts**: Prefer `<Alert variant="..." title="..." description="..." dismissible />` over manual multi-tag nesting.
- **Consistent Spacing**: Use `gap-2`, `gap-4`, `gap-6` consistently.
- **Glassmorphism & Elevation**: Use `backdrop-blur-md bg-background/80` for headers and sticky toolbars.
- **Micro-animations**: Subtle transitions (`transition-all duration-200 ease-in-out`).
- **Cursor Pointer**: Explicitly add `cursor-pointer` on all interactive buttons, cards, and select triggers.
