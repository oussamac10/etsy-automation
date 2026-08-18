<script setup lang="ts">
import { computed } from "vue";
import Button from "./Button.vue";

interface Props {
  currentPage: number;
  totalItems: number;
  pageSize?: number;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  pageSize: 20,
  disabled: false,
});

const emit = defineEmits<{
  (e: "update:currentPage", page: number): void;
  (e: "page-change", page: number): void;
}>();

const totalPages = computed(() => Math.max(1, Math.ceil(props.totalItems / props.pageSize)));

const startItem = computed(() => {
  if (props.totalItems === 0) return 0;
  return (props.currentPage - 1) * props.pageSize + 1;
});

const endItem = computed(() => {
  return Math.min(props.currentPage * props.pageSize, props.totalItems);
});

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value || page === props.currentPage || props.disabled) {
    return;
  }
  emit("update:currentPage", page);
  emit("page-change", page);
}

const displayedPages = computed<(number | string)[]>(() => {
  const total = totalPages.value;
  const current = props.currentPage;

  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [];

  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i);
    pages.push("...");
    pages.push(total);
  } else if (current >= total - 3) {
    pages.push(1);
    pages.push("...");
    for (let i = total - 4; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    pages.push("...");
    pages.push(current - 1);
    pages.push(current);
    pages.push(current + 1);
    pages.push("...");
    pages.push(total);
  }

  return pages;
});
</script>

<template>
  <nav
    v-if="totalItems > 0"
    class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 py-4 px-2 select-none border-t border-border/80"
    role="navigation"
    aria-label="Pagination Navigation"
  >
    <!-- Item Range Indicator -->
    <div class="text-xs text-muted-foreground">
      Showing
      <span class="font-bold text-foreground font-mono">{{ startItem }}</span>
      to
      <span class="font-bold text-foreground font-mono">{{ endItem }}</span>
      of
      <span class="font-bold text-foreground font-mono">{{ totalItems }}</span>
      results
    </div>

    <!-- Navigation Buttons -->
    <div v-if="totalPages > 1" class="flex items-center gap-1.5 self-center sm:self-auto">
      <!-- Previous Button -->
      <Button
        variant="outline"
        size="sm"
        class="h-8 px-2.5 gap-1 text-xs font-semibold cursor-pointer text-secondary-foreground hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage <= 1 || disabled"
        aria-label="Previous Page"
        data-testid="pagination-prev-btn"
        @click="goToPage(currentPage - 1)"
      >
        <Icon name="lucide:chevron-left" class="size-3.5" aria-hidden="true" />
        <span class="hidden sm:inline">Prev</span>
      </Button>

      <!-- Page Numbers -->
      <div class="flex items-center gap-1">
        <template v-for="(p, idx) in displayedPages" :key="idx">
          <span
            v-if="p === '...'"
            class="px-2 text-xs text-muted-foreground font-mono select-none"
            aria-hidden="true"
          >
            …
          </span>
          <button
            v-else
            type="button"
            class="size-8 rounded-lg text-xs font-bold font-mono transition-all flex items-center justify-center cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/40"
            :class="[
              p === currentPage
                ? 'bg-primary text-primary-foreground shadow-xs font-extrabold'
                : 'text-secondary-foreground hover:bg-secondary hover:text-foreground border border-border/60 bg-white',
              disabled ? 'opacity-40 cursor-not-allowed' : ''
            ]"
            :aria-label="`Go to page ${p}`"
            :aria-current="p === currentPage ? 'page' : undefined"
            :disabled="disabled"
            @click="goToPage(Number(p))"
          >
            {{ p }}
          </button>
        </template>
      </div>

      <!-- Next Button -->
      <Button
        variant="outline"
        size="sm"
        class="h-8 px-2.5 gap-1 text-xs font-semibold cursor-pointer text-secondary-foreground hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages || disabled"
        aria-label="Next Page"
        data-testid="pagination-next-btn"
        @click="goToPage(currentPage + 1)"
      >
        <span class="hidden sm:inline">Next</span>
        <Icon name="lucide:chevron-right" class="size-3.5" aria-hidden="true" />
      </Button>
    </div>
  </nav>
</template>
