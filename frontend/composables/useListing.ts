import { ref } from 'vue';
import type { ListingDraft, UpdateListingPayload, Gate3DecisionPayload } from '~/types/listing';
import { getApiErrorMessage, getCsrfHeaders } from '~/utils/api';

export function useListing() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

  const listingDraft = ref<ListingDraft | null>(null);
  const isLoading = ref(false);
  const isSaving = ref(false);
  const isScreening = ref(false);
  const isGeneratingSeo = ref(false);
  const isDecidingGate = ref(false);
  const errorMessage = ref<string | null>(null);

  async function loadListing(workflowId: string): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing`,
        {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to load listing details.');
      return null;
    } finally {
      isLoading.value = false;
    }
  }

  async function updateListing(workflowId: string, payload: UpdateListingPayload): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isSaving.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          body: payload,
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to update listing.');
      throw err;
    } finally {
      isSaving.value = false;
    }
  }

  async function rescreenTrademark(workflowId: string): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isScreening.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/rescreen`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to re-screen trademark risk.');
      throw err;
    } finally {
      isScreening.value = false;
    }
  }

  async function generateSeo(workflowId: string): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isGeneratingSeo.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/generate-seo`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to generate AI SEO copy.');
      throw err;
    } finally {
      isGeneratingSeo.value = false;
    }
  }

  async function decideGate3(workflowId: string, payload: Gate3DecisionPayload): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isDecidingGate.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/gates/listing`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          body: payload,
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to record Gate 3 decision.');
      throw err;
    } finally {
      isDecidingGate.value = false;
    }
  }

  const isBuildingPackage = ref(false);

  async function buildPackage(workflowId: string): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isBuildingPackage.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/package`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to compile customer ZIP package.');
      throw err;
    } finally {
      isBuildingPackage.value = false;
    }
  }

  const isRestoringVersion = ref(false);

  async function restoreVersion(workflowId: string, versionNumber: number): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isRestoringVersion.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/restore-version`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          body: { version: versionNumber },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, `Failed to restore version ${versionNumber}.`);
      throw err;
    } finally {
      isRestoringVersion.value = false;
    }
  }

  const isDeletingVersion = ref(false);

  async function deleteVersion(workflowId: string, versionNumber: number): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isDeletingVersion.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/versions/${versionNumber}`,
        {
          method: 'DELETE',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, `Failed to delete version ${versionNumber}.`);
      throw err;
    } finally {
      isDeletingVersion.value = false;
    }
  }

  const isDeletingTagHistory = ref(false);

  async function deleteTagFromHistory(workflowId: string, tag: string): Promise<ListingDraft | null> {
    if (!workflowId || !tag) return null;
    isDeletingTagHistory.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/tags/history/${encodeURIComponent(tag)}`,
        {
          method: 'DELETE',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, `Failed to delete tag '${tag}' from history.`);
      throw err;
    } finally {
      isDeletingTagHistory.value = false;
    }
  }

  return {
    listingDraft,
    isLoading,
    isSaving,
    isScreening,
    isGeneratingSeo,
    isBuildingPackage,
    isRestoringVersion,
    isDeletingVersion,
    isDeletingTagHistory,
    isDecidingGate,
    errorMessage,
    loadListing,
    updateListing,
    rescreenTrademark,
    generateSeo,
    buildPackage,
    restoreVersion,
    deleteVersion,
    deleteTagFromHistory,
    decideGate3,
  };
}
