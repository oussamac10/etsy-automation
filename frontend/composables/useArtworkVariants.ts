import { ref, computed } from "vue";
import type { ArtworkVariantItem, CreateArtworkVariantPayload } from "~/types/artworkVariants";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";

export function useArtworkVariants() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

  const variants = ref<ArtworkVariantItem[]>([]);
  const isFetching = ref(false);
  const isGenerating = ref(false);
  const isActing = ref(false);
  const actionError = ref<string | null>(null);
  const currentWorkflowId = ref<string | null>(null);
  let latestVariantReqSeq = 0;

  const approvedVariants = computed(() =>
    variants.value.filter((v) => v.variant_status === "approved")
  );

  function resetState() {
    variants.value = [];
    currentWorkflowId.value = null;
    actionError.value = null;
    isFetching.value = false;
    isGenerating.value = false;
    isActing.value = false;
  }

  async function fetchVariants(workflowId: string): Promise<void> {
    if (!workflowId) return;

    if (currentWorkflowId.value !== workflowId) {
      variants.value = [];
      currentWorkflowId.value = workflowId;
    }

    const seq = ++latestVariantReqSeq;
    isFetching.value = true;
    actionError.value = null;
    try {
      const data = await $fetch<ArtworkVariantItem[]>(
        `${apiBase}/api/v1/workflows/${workflowId}/artwork-variants`,
        {
          headers: { Accept: "application/json" },
          credentials: "include",
        }
      );
      if (seq === latestVariantReqSeq && currentWorkflowId.value === workflowId) {
        variants.value = Array.isArray(data) ? data : [];
      }
    } catch (err: unknown) {
      if (seq === latestVariantReqSeq && currentWorkflowId.value === workflowId) {
        actionError.value = getApiErrorMessage(err, "Failed to load artwork color variants.");
        variants.value = [];
      }
    } finally {
      if (seq === latestVariantReqSeq) {
        isFetching.value = false;
      }
    }
  }

  async function generateVariant(
    workflowId: string,
    payload: CreateArtworkVariantPayload
  ): Promise<ArtworkVariantItem | null> {
    if (!workflowId) return null;
    isGenerating.value = true;
    actionError.value = null;
    try {
      const headers = getCsrfHeaders();
      headers["Content-Type"] = "application/json";

      const created = await $fetch<ArtworkVariantItem>(
        `${apiBase}/api/v1/workflows/${workflowId}/artwork-variants`,
        {
          method: "POST",
          headers,
          body: payload,
          credentials: "include",
        }
      );

      variants.value = [created, ...variants.value];
      return created;
    } catch (err: unknown) {
      actionError.value = getApiErrorMessage(err, "Failed to generate color variant.");
      return null;
    } finally {
      isGenerating.value = false;
    }
  }

  async function approveVariant(workflowId: string, variantId: string): Promise<boolean> {
    if (!workflowId || !variantId) return false;
    isActing.value = true;
    actionError.value = null;
    try {
      const headers = getCsrfHeaders();
      const updated = await $fetch<ArtworkVariantItem>(
        `${apiBase}/api/v1/workflows/${workflowId}/artwork-variants/${variantId}/approve`,
        {
          method: "POST",
          headers,
          credentials: "include",
        }
      );

      const idx = variants.value.findIndex((v) => v.id === variantId);
      if (idx >= 0) {
        const copy = [...variants.value];
        copy[idx] = updated;
        variants.value = copy;
      }
      return true;
    } catch (err: unknown) {
      actionError.value = getApiErrorMessage(err, "Failed to approve color variant.");
      return false;
    } finally {
      isActing.value = false;
    }
  }

  async function rejectVariant(workflowId: string, variantId: string): Promise<boolean> {
    if (!workflowId || !variantId) return false;
    isActing.value = true;
    actionError.value = null;
    try {
      const headers = getCsrfHeaders();
      const updated = await $fetch<ArtworkVariantItem>(
        `${apiBase}/api/v1/workflows/${workflowId}/artwork-variants/${variantId}/reject`,
        {
          method: "POST",
          headers,
          credentials: "include",
        }
      );

      const idx = variants.value.findIndex((v) => v.id === variantId);
      if (idx >= 0) {
        const copy = [...variants.value];
        copy[idx] = updated;
        variants.value = copy;
      }
      return true;
    } catch (err: unknown) {
      actionError.value = getApiErrorMessage(err, "Failed to reject color variant.");
      return false;
    } finally {
      isActing.value = false;
    }
  }

  async function deleteVariant(workflowId: string, variantId: string): Promise<boolean> {
    if (!workflowId || !variantId) return false;
    isActing.value = true;
    actionError.value = null;
    try {
      const headers = getCsrfHeaders();
      await $fetch(`${apiBase}/api/v1/workflows/${workflowId}/artwork-variants/${variantId}`, {
        method: "DELETE",
        headers,
        credentials: "include",
      });

      variants.value = variants.value.filter((v) => v.id !== variantId);
      return true;
    } catch (err: unknown) {
      actionError.value = getApiErrorMessage(err, "Failed to delete color variant.");
      return false;
    } finally {
      isActing.value = false;
    }
  }

  async function togglePackageInclusion(
    workflowId: string,
    variantId: string,
    includeInBuyerPackage: boolean
  ): Promise<boolean> {
    if (!workflowId || !variantId) return false;
    isActing.value = true;
    actionError.value = null;
    try {
      const headers = getCsrfHeaders();
      headers["Content-Type"] = "application/json";
      const updated = await $fetch<ArtworkVariantItem>(
        `${apiBase}/api/v1/workflows/${workflowId}/artwork-variants/${variantId}`,
        {
          method: "PATCH",
          headers,
          body: { include_in_buyer_package: includeInBuyerPackage },
          credentials: "include",
        }
      );

      const idx = variants.value.findIndex((v) => v.id === variantId);
      if (idx >= 0) {
        const copy = [...variants.value];
        copy[idx] = updated;
        variants.value = copy;
      }
      return true;
    } catch (err: unknown) {
      actionError.value = getApiErrorMessage(err, "Failed to update buyer package inclusion.");
      return false;
    } finally {
      isActing.value = false;
    }
  }

  return {
    variants,
    approvedVariants,
    isFetching,
    isGenerating,
    isActing,
    actionError,
    fetchVariants,
    generateVariant,
    approveVariant,
    rejectVariant,
    deleteVariant,
    togglePackageInclusion,
    resetState,
  };
}
