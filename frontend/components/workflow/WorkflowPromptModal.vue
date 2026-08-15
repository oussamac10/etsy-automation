<script setup lang="ts">
import { ref, watch } from "vue";
import { AlertCircle } from "lucide-vue-next";
import Dialog from "~/components/ui/Dialog.vue";
import DialogHeader from "~/components/ui/DialogHeader.vue";
import DialogTitle from "~/components/ui/DialogTitle.vue";
import DialogDescription from "~/components/ui/DialogDescription.vue";
import DialogFooter from "~/components/ui/DialogFooter.vue";
import Button from "~/components/ui/Button.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Textarea from "~/components/ui/Textarea.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";

const props = defineProps<{
  open: boolean;
  positivePrompt: string;
  negativePrompt: string;
  slogan: string;
  typography: string;
  changeNote: string;
  isSubmitting: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: {
    positive_prompt: string;
    negative_prompt: string;
    exact_slogan: string;
    typography_instructions: string;
    change_note: string;
  }): void;
}>();

const editPositivePrompt = ref(props.positivePrompt);
const editNegativePrompt = ref(props.negativePrompt);
const editSlogan = ref(props.slogan);
const editTypography = ref(props.typography);
const editChangeNote = ref(props.changeNote);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      editPositivePrompt.value = props.positivePrompt;
      editNegativePrompt.value = props.negativePrompt;
      editSlogan.value = props.slogan;
      editTypography.value = props.typography;
      editChangeNote.value = props.changeNote;
    }
  }
);

function handleSubmit() {
  emit("submit", {
    positive_prompt: editPositivePrompt.value.trim(),
    negative_prompt: editNegativePrompt.value.trim(),
    exact_slogan: editSlogan.value.trim(),
    typography_instructions: editTypography.value.trim(),
    change_note: editChangeNote.value.trim() || "Manual revision",
  });
}
</script>

<template>
  <Dialog :open="open" max-width="xl" @close="emit('close')">
    <DialogHeader>
      <DialogTitle>Revise Design Prompt</DialogTitle>
      <DialogDescription>
        Adjust the generation values. A new version will be appended to support clean trace audit logs.
      </DialogDescription>
    </DialogHeader>

    <Alert v-if="error" variant="destructive" class="my-4">
      <AlertCircle class="h-4 w-4" />
      <AlertDescription>{{ error }}</AlertDescription>
    </Alert>

    <form class="space-y-4 mt-4" @submit.prevent="handleSubmit">
      <div class="space-y-1.5">
        <Label for="revise-positive" required>Positive Prompt</Label>
        <Textarea
          id="revise-positive"
          v-model="editPositivePrompt"
          required
          :rows="4"
        />
      </div>

      <div class="space-y-1.5">
        <Label for="revise-negative" required>Negative Prompt (Required)</Label>
        <Textarea
          id="revise-negative"
          v-model="editNegativePrompt"
          required
          :rows="2"
        />
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <Label for="revise-slogan">Exact Slogan</Label>
          <Input id="revise-slogan" v-model="editSlogan" />
        </div>
        <div class="space-y-1.5">
          <Label for="revise-typography">Typography Instructions</Label>
          <Input id="revise-typography" v-model="editTypography" />
        </div>
      </div>

      <div class="space-y-1.5">
        <Label for="revise-note" required>Reason for Change / Change Note</Label>
        <Input
          id="revise-note"
          v-model="editChangeNote"
          required
          placeholder="e.g. emphasising watercolor texture"
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
          :loading="isSubmitting"
          class="font-bold bg-indigo-600 hover:bg-indigo-700"
        >
          <span>Apply Revision</span>
        </Button>
      </DialogFooter>
    </form>
  </Dialog>
</template>
