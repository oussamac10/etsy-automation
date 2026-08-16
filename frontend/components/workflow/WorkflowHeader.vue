<script setup lang="ts">
import { ref } from "vue";
import Button from "~/components/ui/Button.vue";
import Badge from "~/components/ui/Badge.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import {
  canDelete,
  isStopped,
  needsOwner,
} from "~/composables/useWorkflowControls";

interface Workflow {
  id: string;
  name: string;
  idea_mode: string;
  target_marketplace: string;
  target_country: string;
  output_language: string;
  target_buyer: string | null;
  intended_product_uses: string[];
  state: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface ProductionJob {
  id: string;
  status: string;
}

const props = defineProps<{
  workflow: Workflow;
  latestProductionJob: ProductionJob | null;
  isWorkflowRunning: boolean;
  displayStageLabel: string;
  pendingWorkflowId: string | null;
  controlError: string | null;
}>();

const emit = defineEmits<{
  (e: "control", action: "cancel" | "rerun" | "delete"): void;
}>();

const confirmingDelete = ref(false);

function handleDelete() {
  emit("control", "delete");
}
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-border pb-6">
      <div class="space-y-1.5">
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <NuxtLink to="/" class="flex items-center gap-1 font-semibold text-primary-hover hover:text-[#B33E0B] transition-colors">
            <Icon name="lucide:arrow-left" class="size-3.5" aria-hidden="true" />
            <span>Campaigns</span>
          </NuxtLink>
          <span class="text-border">/</span>
          <Badge variant="secondary" class="text-[10px] px-2 py-0 uppercase">
            {{ workflow.idea_mode }}
          </Badge>
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
          {{ workflow.name }}
        </h1>
        <p class="text-xs text-muted-foreground font-mono">ID: {{ workflow.id }}</p>
      </div>

      <!-- Actions Toolbar -->
      <div class="flex items-center gap-2 flex-wrap">
        <Badge
          :variant="
            workflow.state.endsWith('_APPROVED') || workflow.state === 'ETSY_DRAFT_CREATED' || (workflow.state === 'PRODUCTION' && latestProductionJob?.status === 'SUCCEEDED')
              ? 'success'
              : isWorkflowRunning
                ? 'warning'
                : needsOwner(workflow.state)
                  ? 'default'
                  : workflow.state.endsWith('_FAILED')
                    ? 'destructive'
                    : 'secondary'
          "
          class="px-3 py-1 text-xs gap-1.5 font-semibold inline-flex items-center"
        >
          <span
            v-if="isWorkflowRunning"
            class="h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse"
            aria-hidden="true"
          />
          <Icon
            v-else-if="workflow.state === 'PRODUCTION' && latestProductionJob?.status === 'SUCCEEDED'"
            name="lucide:circle-check"
            class="size-3.5 text-[#2F7D32]"
            aria-hidden="true"
          />
          <span>{{ displayStageLabel }}</span>
        </Badge>

        <Button
          v-if="isWorkflowRunning"
          variant="destructive"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 shadow-2xs font-semibold cursor-pointer inline-flex items-center"
          @click="emit('control', 'cancel')"
        >
          <Icon name="lucide:square" class="size-3.5 fill-current" aria-hidden="true" />
          <span>Stop</span>
        </Button>

        <Button
          v-if="isStopped(workflow.state)"
          variant="default"
          size="sm"
          :disabled="pendingWorkflowId === workflow.id"
          class="gap-1.5 font-semibold shadow-2xs cursor-pointer inline-flex items-center"
          @click="emit('control', 'rerun')"
        >
          <Icon name="lucide:play" class="size-3.5" aria-hidden="true" />
          <span>Resume</span>
        </Button>

        <Button
          v-if="canDelete(workflow.state) && !confirmingDelete"
          variant="outline"
          size="sm"
          class="gap-1.5 text-secondary-foreground hover:text-destructive hover:border-[#FFCDD2] hover:bg-[#FFEBEE] cursor-pointer inline-flex items-center"
          @click="confirmingDelete = true"
        >
          <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
          <span>Delete</span>
        </Button>

        <span
          v-else-if="confirmingDelete"
          class="inline-flex items-center gap-2 rounded-lg border border-[#FFCDD2] bg-[#FFEBEE] px-3 py-1.5 text-xs text-destructive"
        >
          <span>Delete this campaign?</span>
          <Button
            variant="destructive"
            size="sm"
            :disabled="pendingWorkflowId === workflow.id"
            class="h-6 px-2 text-[11px] cursor-pointer"
            @click="handleDelete"
          >
            Delete
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 px-2 text-[11px] cursor-pointer"
            @click="confirmingDelete = false"
          >
            Keep
          </Button>
        </span>
      </div>
    </header>

    <Alert v-if="controlError" variant="destructive">
      <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
      <AlertDescription>{{ controlError }}</AlertDescription>
    </Alert>
  </div>
</template>
