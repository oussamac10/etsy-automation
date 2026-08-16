<script setup lang="ts">
import { ref } from "vue";
import Button from "~/components/ui/Button.vue";

defineProps<{
  productLabel: string;
  hasFile: boolean;
  fileName?: string;
}>();

const emit = defineEmits<{
  (e: "fileSelected", file: File): void;
  (e: "removeFile"): void;
  (e: "openCrop"): void;
}>();

const isDragging = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

function handleFileChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    emit("fileSelected", target.files[0]);
  }
}

function handleDrop(event: DragEvent): void {
  isDragging.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    emit("fileSelected", event.dataTransfer.files[0]);
  }
}
</script>

<template>
  <div>
    <!-- Dropzone Area -->
    <div
      v-if="!hasFile"
      class="border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-3"
      :class="isDragging ? 'border-indigo-500 bg-indigo-50/50 scale-[0.99]' : 'border-zinc-300 hover:border-indigo-400 bg-zinc-50/50 hover:bg-indigo-50/20'"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="fileInputRef?.click()"
    >
      <input
        ref="fileInputRef"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        class="hidden"
        @change="handleFileChange"
      >
      <div class="h-12 w-12 rounded-full bg-indigo-100/80 text-indigo-600 flex items-center justify-center shadow-xs">
        <Icon name="lucide:upload-cloud" class="size-6" aria-hidden="true" />
      </div>
      <div class="space-y-1">
        <p class="text-sm font-bold text-zinc-800">
          Click to upload or drag & drop {{ productLabel }} photo
        </p>
        <p class="text-xs text-zinc-500">
          Supports JPEG, PNG, WEBP (up to 40 MB). High resolution recommended.
        </p>
      </div>
    </div>

    <!-- Uploaded File Header -->
    <div v-else class="flex items-center justify-between p-3 rounded-xl bg-zinc-50 border border-zinc-200">
      <div class="flex items-center gap-2 truncate">
        <Icon name="lucide:image" class="size-4 text-indigo-600 shrink-0" aria-hidden="true" />
        <span class="text-xs font-bold text-zinc-900 truncate">{{ fileName || 'Uploaded Photo' }}</span>
      </div>
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          class="text-xs h-7 px-2 cursor-pointer inline-flex items-center gap-1 text-indigo-700 bg-indigo-50/60 border-indigo-200 hover:bg-indigo-100/80"
          @click="emit('openCrop')"
        >
          <Icon name="lucide:crop" class="size-3" aria-hidden="true" />
          <span>Crop Photo</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          class="text-xs h-7 px-2 cursor-pointer inline-flex items-center gap-1"
          @click="fileInputRef?.click()"
        >
          <Icon name="lucide:refresh-cw" class="size-3" aria-hidden="true" />
          <span>Change</span>
        </Button>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          class="hidden"
          @change="handleFileChange"
        >
      </div>
    </div>
  </div>
</template>
