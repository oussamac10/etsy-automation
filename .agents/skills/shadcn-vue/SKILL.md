---
name: shadcn-vue
description: >-
  Expert guide for implementing shadcn-vue and Radix-Vue component patterns in Nuxt 3
  and Vue 3. Covers reusable UI components (Buttons, Cards, Dialogs, Badges, Tabs,
  Tooltips, Forms, Carousels, Dropdowns), accessible primitives, Lucide icons, and
  Tailwind CSS design tokens. Activate whenever building or refactoring frontend UI components.
---

# shadcn-vue & Accessible Component Architecture

Always build frontend components following **shadcn-vue** design principles: accessible, copy-pasteable, customizable components built on top of unstyled primitives (Radix Vue) and styled with Tailwind CSS utility classes.

---

## 1. Core Principles

1. **Accessible Primitives**: Use accessible attributes (`aria-*`, `role`, keyboard navigation, focus rings).
2. **Variants with `class-variance-authority` (cva)** or concise Tailwind composable classes:
   - Primary, Secondary, Destructive, Outline, Ghost, Link variants.
   - Sizing scales (`sm`, `md`, `lg`, `icon`).
3. **Clean Composition**:
   - Split complex components into logical sub-components (e.g. `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`).
4. **Lucide Icons**: Use Lucide icons with consistent stroke-width (1.5 - 2px) and sizing (`w-4 h-4`, `w-5 h-5`).

---

## 2. Standard Component Patterns

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
      'inline-flex items-center justify-center rounded-md font-medium transition-colors',
      'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
      'disabled:pointer-events-none disabled:opacity-50',
      variantClasses[variant],
      sizeClasses[size]
    ]"
  >
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
  variant?: 'default' | 'secondary' | 'outline' | 'destructive' | 'success'
}>()
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring',
      variant === 'secondary' ? 'bg-secondary text-secondary-foreground' :
      variant === 'outline' ? 'border border-input text-foreground' :
      variant === 'destructive' ? 'bg-destructive/15 text-destructive border border-destructive/30' :
      variant === 'success' ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30' :
      'bg-primary text-primary-foreground'
    ]"
  >
    <slot />
  </span>
</template>
```

---

## 3. UI Guidelines

- **Consistent Spacing**: Use `gap-2`, `gap-4`, `gap-6` consistently.
- **Glassmorphism & Elevation**: Use `backdrop-blur-md bg-background/80` for headers and sticky toolbars.
- **Micro-animations**: Subtle transitions (`transition-all duration-200 ease-in-out`).
