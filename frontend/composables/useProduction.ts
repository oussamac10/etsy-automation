import { ref, onUnmounted } from "vue";
import type { ProductionJob } from "~/types/production";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";

export function useProduction() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

  const latestProductionJob = ref<ProductionJob | null>(null);
  const isTriggeringProduction = ref(false);
  const isPolling = ref(false);
  const productionError = ref<string | null>(null);

  let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;
  let isUnmounted = false;

  function stopPolling() {
    if (pollTimeoutId) {
      clearTimeout(pollTimeoutId);
      pollTimeoutId = null;
    }
    isPolling.value = false;
  }

  async function loadProductionJob(workflowId: string): Promise<ProductionJob | null> {
    if (!workflowId) return null;
    try {
      const data = await $fetch<ProductionJob>(
        `${apiBase}/api/v1/workflows/${workflowId}/production`,
        {
          headers: { Accept: "application/json" },
          credentials: "include",
        }
      );
      if (data) {
        latestProductionJob.value = data;
        return data;
      }
    } catch {
      // 404 is normal before production runs
    }
    return null;
  }

  function startPolling(workflowId: string, onCompleted?: (job: ProductionJob) => void | Promise<void>) {
    stopPolling();
    isPolling.value = true;

    async function pollStep() {
      if (isUnmounted || !isPolling.value) return;

      try {
        const job = await loadProductionJob(workflowId);
        if (job) {
          if (job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELLED") {
            stopPolling();
            // Authoritative final hydration
            await loadProductionJob(workflowId);
            if (onCompleted) {
              await onCompleted(job);
            }
            return;
          }
        }
      } catch (err) {
        console.error("Production polling error:", err);
      }

      if (!isUnmounted && isPolling.value) {
        pollTimeoutId = setTimeout(pollStep, 2000);
      }
    }

    pollStep();
  }

  async function triggerProduction(
    workflowId: string,
    candidateAssetId?: string,
    onCompleted?: (job: ProductionJob) => void | Promise<void>
  ): Promise<ProductionJob | null> {
    if (!workflowId) return null;
    isTriggeringProduction.value = true;
    productionError.value = null;

    try {
      const queryParams = candidateAssetId ? `?candidate_asset_id=${candidateAssetId}` : "";
      const job = await $fetch<ProductionJob>(
        `${apiBase}/api/v1/workflows/${workflowId}/production${queryParams}`,
        {
          method: "POST",
          headers: getCsrfHeaders(),
          credentials: "include",
        }
      );
      latestProductionJob.value = job;
      startPolling(workflowId, onCompleted);
      return job;
    } catch (err: unknown) {
      productionError.value = getApiErrorMessage(err, "Failed to start master PNG production.");
      throw err;
    } finally {
      isTriggeringProduction.value = false;
    }
  }

  onUnmounted(() => {
    isUnmounted = true;
    stopPolling();
  });

  return {
    latestProductionJob,
    isTriggeringProduction,
    isPolling,
    productionError,
    loadProductionJob,
    triggerProduction,
    startPolling,
    stopPolling,
  };
}
