---
name: frontend-testing
description: >-
  Guide for robust frontend unit, integration, and component testing with Vitest,
  @vue/test-utils, and Playwright in Nuxt 3 / Vue 3 applications. Use when writing,
  debugging, or maintaining frontend test suites.
---

# Frontend Testing with Vitest & Vue Test Utils

Patterns for writing fast, resilient, and maintainable unit and component tests in Nuxt 3.

---

## 1. Component Testing with Vitest & @vue/test-utils

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MyComponent from '../components/MyComponent.vue'

describe('MyComponent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders props and triggers action on click', async () => {
    const wrapper = mount(MyComponent, {
      props: {
        title: 'Test Title',
        disabled: false
      }
    })

    expect(wrapper.text()).toContain('Test Title')

    const button = wrapper.find('button')
    await button.trigger('click')

    expect(wrapper.emitted('action')).toBeTruthy()
  })
})
```

---

## 2. Mocking Nuxt Globals & Composables

Always mock `$fetch`, `useRuntimeConfig`, `useRoute`, and `useRouter` cleanly:

```typescript
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBase: 'http://localhost:8000'
  }
}))

vi.stubGlobal('$fetch', vi.fn())
```
