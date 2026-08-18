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

  return {
    listingDraft,
    isLoading,
    isSaving,
    isScreening,
    isGeneratingSeo,
    isDecidingGate,
    errorMessage,
    loadListing,
    updateListing,
    rescreenTrademark,
    generateSeo,
    decideGate3,
  };
}
