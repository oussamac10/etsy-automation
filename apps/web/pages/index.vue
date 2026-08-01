<script setup lang="ts">
import { fetchApiHealth, type ApiHealth } from "~/composables/useApiHealth";
import { FALLBACK_STATES, fetchWorkflow } from "~/composables/useWorkflow";
import { useWorkflowStore } from "~/stores/workflow";

/**
 * Phase 1 dashboard: it proves the stack is wired together and states the
 * product rules that the rest of the build must keep. No paid action exists
 * here yet.
 */

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;
const store = useWorkflowStore();

const health = ref<ApiHealth | null>(null);
const healthError = ref<string | null>(null);
const isLoading = ref(true);

async function load(): Promise<void> {
  isLoading.value = true;
  store.beginLoading();
  healthError.value = null;

  const [healthResult, workflowResult] = await Promise.allSettled([
    fetchApiHealth(apiBase),
    fetchWorkflow(apiBase),
  ]);

  if (healthResult.status === "fulfilled") {
    health.value = healthResult.value;
  } else {
    health.value = null;
    healthError.value = "The API could not be reached.";
  }

  if (workflowResult.status === "fulfilled") {
    store.setStates(workflowResult.value.states);
  } else {
    store.setError("The workflow description could not be loaded.");
  }

  isLoading.value = false;
}

onMounted(load);

const components = computed(() => Object.entries(health.value?.components ?? {}));
const displayedStates = computed(() =>
  store.isReady ? store.states : [...FALLBACK_STATES],
);
</script>

<template>
  <main id="main" class="mx-auto max-w-4xl px-6 py-12">
    <header class="mb-10">
      <h1 class="text-3xl font-semibold tracking-tight">Etsy PNG Automation</h1>
      <p class="mt-2 max-w-2xl text-slate-600">
        Prepares original PNG products for one Etsy shop. It creates drafts only —
        it never publishes or activates a listing, and it makes no claim that an
        idea is profitable or free of third-party rights.
      </p>
    </header>

    <section aria-labelledby="status-heading" class="mb-10">
      <h2 id="status-heading" class="mb-3 text-xl font-medium">Service status</h2>

      <p v-if="isLoading" data-testid="status-loading" class="text-slate-600">
        Checking services…
      </p>

      <div
        v-else-if="healthError"
        role="alert"
        data-testid="status-error"
        class="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-900"
      >
        <p>{{ healthError }}</p>
        <button
          type="button"
          class="mt-2 rounded border border-red-400 px-3 py-1 font-medium hover:bg-red-100"
          @click="load"
        >
          Retry
        </button>
      </div>

      <ul v-else class="space-y-2" data-testid="status-list">
        <ServiceStatus
          name="api"
          :status="health?.status ?? 'unknown'"
          data-testid="status-api"
        />
        <ServiceStatus
          v-for="[name, component] in components"
          :key="name"
          :name="name"
          :status="component.status"
          :detail="component.detail"
          :latency-ms="component.latency_ms"
        />
      </ul>
    </section>

    <section aria-labelledby="workflow-heading" class="mb-10">
      <h2 id="workflow-heading" class="mb-3 text-xl font-medium">Workflow</h2>
      <p
        v-if="store.loadState === 'error'"
        role="status"
        class="mb-3 text-sm text-amber-900"
      >
        {{ store.errorMessage }} Showing the pipeline this build knows about.
      </p>
      <ol class="flex flex-wrap gap-2" data-testid="workflow-states">
        <li
          v-for="(state, index) in displayedStates"
          :key="state"
          class="rounded-full border border-slate-300 bg-white px-3 py-1 text-sm"
        >
          <span class="mr-1 font-mono text-xs text-slate-500">{{ index + 1 }}</span>
          {{ state }}
        </li>
      </ol>
    </section>

    <section aria-labelledby="gates-heading">
      <h2 id="gates-heading" class="mb-3 text-xl font-medium">
        Human approval gates
      </h2>
      <p class="mb-3 text-slate-600">
        Three decisions always belong to a person. None of them can be skipped or
        automated.
      </p>
      <ol class="list-decimal space-y-1 pl-6" data-testid="gate-list">
        <li>Idea approval</li>
        <li>Artwork approval</li>
        <li>Trademark acknowledgement and final listing approval</li>
      </ol>
    </section>
  </main>
</template>
