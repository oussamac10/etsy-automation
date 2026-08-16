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
      :class="isDragging ? 'border-primary bg-secondary/80 scale-[0.99]' : 'border-border hover:border-primary/60 bg-secondary/30 hover:bg-secondary/60'"
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
      <div class="h-12 w-12 rounded-full bg-secondary border border-border text-primary flex items-center justify-center shadow-xs">
        <Icon name="lucide:upload-cloud" class="size-6" aria-hidden="true" />
      </div>
      <div class="space-y-1">
        <p class="text-sm font-bold text-foreground">
          Click to upload or drag & drop {{ productLabel }} photo
        </p>
        <p class="text-xs text-muted-foreground">
          Supports JPEG, PNG, WEBP (up to 40 MB). High resolution recommended.
        </p>
      </div>
    </div>

    <!-- Uploaded File Header -->
    <div v-else class="flex items-center justify-between p-3 rounded-xl bg-secondary/40 border border-border">
      <div class="flex items-center gap-2 truncate">
        <Icon name="lucide:image" class="size-4 text-primary shrink-0" aria-hidden="true" />
        <span class="text-xs font-bold text-foreground truncate">{{ fileName || 'Uploaded Photo' }}</span>
      </div>
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          class="text-xs h-7 px-2 cursor-pointer inline-flex items-center gap-1 text-primary bg-blue-50 border border-blue-200 hover:bg-blue-100"
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
