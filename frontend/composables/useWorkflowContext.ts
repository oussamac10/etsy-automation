import { ref, computed } from "vue";
import type { WorkflowContextResponse } from "~/types/workflowContext";
import { getApiErrorMessage } from "~/utils/api";

export function useWorkflowContext() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

  const currentWorkflowId = ref<string | null>(null);
  const contextData = ref<WorkflowContextResponse | null>(null);
  const isLoading = ref(false);
  const errorMessage = ref<string | null>(null);

  // Request sequencing token to prevent stale async responses
  let latestRequestSeq = 0;

  function resetState() {
    contextData.value = null;
    currentWorkflowId.value = null;
    errorMessage.value = null;
    isLoading.value = false;
  }

  async function fetchContext(workflowId: string): Promise<WorkflowContextResponse | null> {
    if (!workflowId) return null;

    if (currentWorkflowId.value !== workflowId) {
      contextData.value = null;
      currentWorkflowId.value = workflowId;
    }

    const seq = ++latestRequestSeq;
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<WorkflowContextResponse>(
        `${apiBase}/api/v1/workflows/${workflowId}/context`,
        {
          headers: { Accept: "application/json" },
          credentials: "include",
        }
      );

      // Only update if this request is still the latest one for this workflow
      if (seq === latestRequestSeq && currentWorkflowId.value === workflowId) {
        contextData.value = data;
        return data;
      }
      return null;
    } catch (err: unknown) {
      if (seq === latestRequestSeq && currentWorkflowId.value === workflowId) {
        errorMessage.value = getApiErrorMessage(err, "Failed to load workflow context integrity.");
      }
      return null;
    } finally {
      if (seq === latestRequestSeq) {
        isLoading.value = false;
      }
    }
  }

  const isStale = computed(() => Boolean(contextData.value?.staleness?.is_any_stale));
  const staleReasons = computed(() => contextData.value?.staleness?.stale_reasons || []);
  const conceptStatus = computed(() => contextData.value?.staleness?.concept_status || "CURRENT");
  const artworkStatus = computed(() => contextData.value?.staleness?.artwork_status || "CURRENT");
  const productionStatus = computed(() => contextData.value?.staleness?.production_status || "CURRENT");
  const mockupsStatus = computed(() => contextData.value?.staleness?.mockups_status || "CURRENT");
  const listingStatus = computed(() => contextData.value?.staleness?.listing_status || "CURRENT");
  const packageStatus = computed(() => contextData.value?.staleness?.package_status || "CURRENT");
  const etsySyncStatus = computed(() => contextData.value?.staleness?.etsy_sync_status || "CURRENT");

  return {
    contextData,
    isLoading,
    errorMessage,
    isStale,
    staleReasons,
    conceptStatus,
    artworkStatus,
    productionStatus,
    mockupsStatus,
    listingStatus,
    packageStatus,
    etsySyncStatus,
    fetchContext,
    resetState,
  };
}
