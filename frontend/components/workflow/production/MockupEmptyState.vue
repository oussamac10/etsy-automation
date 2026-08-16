<script setup lang="ts">
import Button from "~/components/ui/Button.vue";

defineProps<{
  productLabel?: string;
  isActionLoading?: boolean;
}>();

const emit = defineEmits<{
  (e: "addMockup"): void;
}>();
</script>

<template>
  <div class="py-12 px-4 rounded-xl border border-dashed border-zinc-200 bg-zinc-50/50 text-center space-y-4">
    <div class="h-12 w-12 rounded-full bg-zinc-100 flex items-center justify-center mx-auto text-zinc-500 shadow-2xs">
      <Icon name="lucide:images" class="size-6 text-zinc-400" aria-hidden="true" />
    </div>
    <div class="space-y-1 max-w-sm mx-auto">
      <h4 class="text-sm font-bold text-zinc-800">
        {{ productLabel ? `No mockups for ${productLabel} yet` : "No mockups selected yet" }}
      </h4>
      <p class="text-xs text-zinc-500 leading-relaxed">
        {{
          productLabel
            ? `Upload your own high-resolution ${productLabel} photos or choose a saved template from your library.`
            : "Add your own product photos and position your master artwork for Etsy listing previews."
        }}
      </p>
    </div>
    <Button
      variant="default"
      size="sm"
      class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold gap-2 shadow-xs cursor-pointer inline-flex items-center"
      :disabled="isActionLoading"
      @click="emit('addMockup')"
    >
      <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
      <span>Add Mockup</span>
    </Button>
  </div>
</template>
