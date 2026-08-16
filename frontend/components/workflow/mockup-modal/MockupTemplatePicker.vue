<script setup lang="ts">
import { ref, computed } from "vue";
import type { MockupTemplateItem } from "~/types/mockup";
import Button from "~/components/ui/Button.vue";

const props = defineProps<{
  templates: MockupTemplateItem[];
  selectedTemplateId: string | null;
  productLabel: string;
  isFetchingTemplates: boolean;
}>();

const emit = defineEmits<{
  (e: "select", template: MockupTemplateItem): void;
  (e: "delete", templateId: string): void;
  (e: "switchToUpload"): void;
}>();

const showAll = ref(false);

// Show max 3 templates by default unless expanded
const visibleTemplates = computed(() => {
  if (showAll.value || props.templates.length <= 3) {
    return props.templates;
  }
  return props.templates.slice(0, 3);
});

const remainingCount = computed(() => Math.max(0, props.templates.length - 3));
</script>

<template>
  <div class="space-y-2">
    <!-- Template Thumbnails Strip -->
    <div v-if="templates.length > 0" class="space-y-1.5">
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-foreground flex items-center gap-1.5">
          <Icon name="lucide:layout-grid" class="size-3.5 text-primary" aria-hidden="true" />
          <span>{{ productLabel }} Blank Templates ({{ templates.length }})</span>
        </span>
        <button
          v-if="templates.length > 3"
          type="button"
          class="text-xs text-primary hover:text-primary-hover font-semibold inline-flex items-center gap-1 cursor-pointer"
          @click="showAll = !showAll"
        >
          <span>{{ showAll ? 'Collapse' : `+ ${remainingCount} More` }}</span>
          <Icon :name="showAll ? 'lucide:chevron-up' : 'lucide:chevron-down'" class="size-3" aria-hidden="true" />
        </button>
      </div>

      <!-- Compact Horizontal Chips / Mini Cards -->
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="tpl in visibleTemplates"
          :key="tpl.id"
          type="button"
          class="group relative flex items-center gap-2.5 p-1.5 pr-3 rounded-xl border-2 transition-all cursor-pointer text-left bg-white shadow-2xs hover:shadow-xs"
          :class="
            selectedTemplateId === tpl.id
              ? 'border-primary ring-2 ring-primary/20 bg-blue-50/40'
              : 'border-border hover:border-primary/40'
          "
          @click="emit('select', tpl)"
        >
          <!-- Compact Thumbnail -->
          <div class="size-11 rounded-lg bg-secondary/50 overflow-hidden relative shrink-0 border border-border shadow-2xs">
            <img
              :src="tpl.url || tpl.preview_url"
              :alt="tpl.name"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform"
            >
            <div
              v-if="selectedTemplateId === tpl.id"
              class="absolute inset-0 bg-primary/40 backdrop-blur-[0.5px] flex items-center justify-center"
            >
              <div class="size-4 rounded-full bg-white text-primary flex items-center justify-center shadow-xs">
                <Icon name="lucide:check" class="size-2.5 stroke-[3]" />
              </div>
            </div>
          </div>

          <!-- Template Name & Details -->
          <div class="max-w-[130px] sm:max-w-[160px] truncate">
            <span class="text-xs font-bold text-foreground truncate block leading-tight">
              {{ tpl.name }}
            </span>
            <span class="text-[10px] text-muted-foreground font-medium capitalize">
              {{ tpl.placement?.blend_mode || 'multiply' }} blend
            </span>
          </div>
        </button>

        <!-- Compact "+ X More" Expand Tile -->
        <button
          v-if="!showAll && remainingCount > 0"
          type="button"
          class="h-[52px] px-3.5 rounded-xl border-2 border-dashed border-border hover:border-primary/50 hover:bg-slate-100 text-secondary-foreground hover:text-primary flex items-center gap-1.5 transition-all cursor-pointer text-xs font-bold"
          @click="showAll = true"
        >
          <Icon name="lucide:plus" class="size-3.5 text-primary" aria-hidden="true" />
          <span>{{ remainingCount }} More</span>
        </button>
      </div>
    </div>

    <!-- Empty Template Library State -->
    <div v-else-if="!isFetchingTemplates" class="py-4 px-4 rounded-xl border border-dashed border-border bg-slate-50 text-center space-y-1.5">
      <div class="size-7 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-muted-foreground">
        <Icon name="lucide:folder-open" class="size-3.5" aria-hidden="true" />
      </div>
      <div class="space-y-0.5">
        <h5 class="text-xs font-bold text-foreground">No saved templates for {{ productLabel }}</h5>
        <p class="text-[10px] text-muted-foreground">Upload a blank photo to customize print placement.</p>
      </div>
      <Button
        variant="outline"
        size="sm"
        class="text-xs font-semibold gap-1.5 h-6.5 px-2.5 cursor-pointer inline-flex items-center"
        @click="emit('switchToUpload')"
      >
        <Icon name="lucide:upload" class="size-3" aria-hidden="true" />
        <span>Upload Photo</span>
      </Button>
    </div>
  </div>
</template>
