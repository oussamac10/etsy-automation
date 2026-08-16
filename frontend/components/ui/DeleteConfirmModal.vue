<script setup lang="ts">
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description: string;
    itemName?: string;
    itemCategory?: string;
    imageUrl?: string | null;
    isDeleting?: boolean;
    error?: string | null;
    confirmText?: string;
  }>(),
  {
    confirmText: "Delete Permanently",
    itemName: "",
    itemCategory: "",
    imageUrl: null,
    isDeleting: false,
    error: null,
  }
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm"): void;
}>();
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 select-none"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-2xl shadow-2xl border border-zinc-200 max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
      <!-- Header -->
      <div class="flex items-center gap-3 text-rose-600">
        <div class="h-10 w-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center shrink-0">
          <Icon name="lucide:trash-2" class="size-5 text-rose-600" aria-hidden="true" />
        </div>
        <div>
          <h3 class="text-sm font-bold text-zinc-900 leading-tight">{{ title }}</h3>
          <p class="text-xs text-zinc-500">{{ description }}</p>
        </div>
      </div>

      <!-- Preview Item Card -->
      <div v-if="itemName || imageUrl" class="p-3 rounded-xl bg-zinc-50 border border-zinc-200/80 flex items-center gap-3">
        <img
          v-if="imageUrl"
          :src="imageUrl"
          alt="Thumbnail"
          class="h-12 w-12 object-cover rounded-lg border border-zinc-200 shrink-0 bg-white"
        >
        <div class="truncate">
          <p class="text-xs font-bold text-zinc-900 truncate">{{ itemName || 'Item' }}</p>
          <p v-if="itemCategory" class="text-[10px] text-zinc-500">{{ itemCategory }}</p>
        </div>
      </div>

      <!-- Error Alert if any -->
      <Alert v-if="error" variant="destructive" class="py-2">
        <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
        <AlertDescription class="text-xs">{{ error }}</AlertDescription>
      </Alert>

      <!-- Actions -->
      <div class="flex justify-end gap-2 pt-2 border-t border-zinc-100">
        <Button
          variant="outline"
          size="sm"
          class="h-8 rounded-md px-3 text-xs cursor-pointer font-medium"
          :disabled="isDeleting"
          @click="emit('close')"
        >
          Cancel
        </Button>
        <Button
          variant="destructive"
          size="sm"
          class="h-8 rounded-md px-3 text-xs font-bold gap-1 cursor-pointer bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white shadow-sm inline-flex items-center"
          :disabled="isDeleting"
          @click="emit('confirm')"
        >
          <Icon v-if="isDeleting" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
          <span>{{ isDeleting ? "Deleting..." : confirmText }}</span>
        </Button>
      </div>
    </div>
  </div>
</template>
