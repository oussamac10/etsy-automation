<script setup lang="ts">
import { ref, watch } from "vue";
import Dialog from "~/components/ui/Dialog.vue";
import DialogHeader from "~/components/ui/DialogHeader.vue";
import DialogTitle from "~/components/ui/DialogTitle.vue";
import DialogDescription from "~/components/ui/DialogDescription.vue";
import DialogFooter from "~/components/ui/DialogFooter.vue";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Textarea from "~/components/ui/Textarea.vue";

const props = defineProps<{
  open: boolean;
  prompt: string;
  changeNote: string;
  isLoading: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: { prompt: string; change_note: string }): void;
}>();

const refinePrompt = ref(props.prompt);
const refineChangeNote = ref(props.changeNote);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      refinePrompt.value = props.prompt;
      refineChangeNote.value = props.changeNote;
    }
  }
);

function handleSubmit() {
  if (!refinePrompt.value.trim() || !refineChangeNote.value.trim()) return;
  emit("submit", {
    prompt: refinePrompt.value.trim(),
    change_note: refineChangeNote.value.trim(),
  });
}
</script>

<template>
  <Dialog :open="open" max-width="lg" @close="emit('close')">
    <DialogHeader>
      <DialogTitle>Refine Artwork Candidate</DialogTitle>
      <DialogDescription>
        Submit an image-to-image refinement using this candidate as reference.
      </DialogDescription>
    </DialogHeader>

    <form class="space-y-4 mt-4" @submit.prevent="handleSubmit">
      <div class="space-y-1.5">
        <Label for="refine-prompt" required>Refinement Instructions</Label>
        <Textarea
          id="refine-prompt"
          v-model="refinePrompt"
          required
          :rows="4"
          placeholder="Describe how to adjust the design (e.g. 'Add a border around text, make colors more vibrant')"
        />
      </div>

      <div class="space-y-1.5">
        <Label for="refine-change-note" required>Change Note</Label>
        <Input
          id="refine-change-note"
          v-model="refineChangeNote"
          required
          placeholder="Brief label for this revision (e.g. 'More vibrant colors')"
        />
      </div>

      <DialogFooter>
        <Button variant="outline" size="sm" type="button" @click="emit('close')">
          Cancel
        </Button>
        <Button
          type="submit"
          variant="default"
          size="sm"
          :loading="isLoading"
          class="font-bold cursor-pointer"
        >
          <span>Submit Refinement</span>
        </Button>
      </DialogFooter>
    </form>
  </Dialog>
</template>
