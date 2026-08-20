import { ref } from 'vue';
import type {
  ListingDraft,
  UpdateListingPayload,
  Gate3DecisionPayload,
  TaxonomyCategory,
  ShopSection,
  TaxonomyProperty,
  PriceRecommendation,
} from '~/types/listing';
import { getApiErrorMessage, getCsrfHeaders } from '~/utils/api';

export function useListing() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

  const listingDraft = ref<ListingDraft | null>(null);
  const shopSections = ref<ShopSection[]>([]);
  const taxonomyProperties = ref<TaxonomyProperty[]>([]);
  const priceRecommendation = ref<PriceRecommendation | null>(null);

  const isLoading = ref(false);
  const isSaving = ref(false);
  const isScreening = ref(false);
  const isGeneratingSeo = ref(false);
  const isDecidingGate = ref(false);
  const isUpdatingTaxonomy = ref(false);
  const isLoadingTaxonomy = ref(false);
  const isLoadingSections = ref(false);
  const isCreatingSection = ref(false);
  const isLoadingProperties = ref(false);
  const isLoadingPriceRec = ref(false);
  const isBuildingPackage = ref(false);
  const isRestoringVersion = ref(false);
  const isDeletingVersion = ref(false);
  const isDeletingTagHistory = ref(false);
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

  async function fetchPriceRecommendation(workflowId: string): Promise<PriceRecommendation | null> {
    if (!workflowId) return null;
    isLoadingPriceRec.value = true;
    try {
      const data = await $fetch<PriceRecommendation>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/price-recommendation`,
        {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        }
      );
      priceRecommendation.value = data;
      return data;
    } catch {
      return null;
    } finally {
      isLoadingPriceRec.value = false;
    }
  }

  async function fetchShopSections(workflowId: string): Promise<ShopSection[]> {
    if (!workflowId) return [];
    isLoadingSections.value = true;
    try {
      const data = await $fetch<ShopSection[]>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/shop-sections`,
        {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        }
      );
      shopSections.value = data || [];
      return shopSections.value;
    } catch {
      return [];
    } finally {
      isLoadingSections.value = false;
    }
  }

  async function createShopSection(workflowId: string, title: string): Promise<ShopSection | null> {
    if (!workflowId || !title.trim()) return null;
    isCreatingSection.value = true;
    try {
      const data = await $fetch<ShopSection>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/shop-sections`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          body: { title: title.trim() },
          credentials: 'include',
        }
      );
      if (data) {
        shopSections.value = [...shopSections.value, data];
      }
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to create shop section on Etsy.');
      throw err;
    } finally {
      isCreatingSection.value = false;
    }
  }

  async function fetchTaxonomyProperties(workflowId: string): Promise<TaxonomyProperty[]> {
    if (!workflowId) return [];
    isLoadingProperties.value = true;
    try {
      const data = await $fetch<TaxonomyProperty[]>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/taxonomy-properties`,
        {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        }
      );
      taxonomyProperties.value = data || [];
      return taxonomyProperties.value;
    } catch {
      return [];
    } finally {
      isLoadingProperties.value = false;
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
      errorMessage.value = getApiErrorMessage(err, 'Failed to generate SEO listing.');
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
        `${apiBase}/api/v1/workflows/${workflowId}/gates/gate-3/decision`,
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
      errorMessage.value = getApiErrorMessage(err, 'Failed to submit Gate 3 decision.');
      throw err;
    } finally {
      isDecidingGate.value = false;
    }
  }

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
      errorMessage.value = getApiErrorMessage(err, 'Failed to generate customer download package.');
      throw err;
    } finally {
      isBuildingPackage.value = false;
    }
  }

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
      errorMessage.value = getApiErrorMessage(err, 'Failed to restore listing version.');
      throw err;
    } finally {
      isRestoringVersion.value = false;
    }
  }

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
      errorMessage.value = getApiErrorMessage(err, 'Failed to delete listing version.');
      throw err;
    } finally {
      isDeletingVersion.value = false;
    }
  }

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
      errorMessage.value = getApiErrorMessage(err, 'Failed to remove tag from history.');
      throw err;
    } finally {
      isDeletingTagHistory.value = false;
    }
  }

  async function fetchTaxonomyCategories(workflowId: string, query?: string): Promise<TaxonomyCategory[]> {
    if (!workflowId) return [];
    isLoadingTaxonomy.value = true;
    try {
      const url = query && query.trim()
        ? `${apiBase}/api/v1/workflows/${workflowId}/listing/taxonomy/categories?q=${encodeURIComponent(query.trim())}`
        : `${apiBase}/api/v1/workflows/${workflowId}/listing/taxonomy/categories`;

      const data = await $fetch<TaxonomyCategory[]>(url, {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      });
      return data || [];
    } catch {
      return [];
    } finally {
      isLoadingTaxonomy.value = false;
    }
  }

  async function updateTaxonomy(workflowId: string, taxonomyId: number, taxonomyPath?: string): Promise<ListingDraft | null> {
    if (!workflowId) return null;
    isUpdatingTaxonomy.value = true;
    errorMessage.value = null;
    try {
      const data = await $fetch<ListingDraft>(
        `${apiBase}/api/v1/workflows/${workflowId}/listing/taxonomy`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          body: {
            taxonomy_id: taxonomyId,
            taxonomy_path: taxonomyPath,
          },
          credentials: 'include',
        }
      );
      listingDraft.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to update taxonomy category.');
      throw err;
    } finally {
      isUpdatingTaxonomy.value = false;
    }
  }

  return {
    listingDraft,
    shopSections,
    taxonomyProperties,
    priceRecommendation,
    isLoading,
    isSaving,
    isScreening,
    isGeneratingSeo,
    isBuildingPackage,
    isRestoringVersion,
    isDeletingVersion,
    isDeletingTagHistory,
    isDecidingGate,
    isUpdatingTaxonomy,
    isLoadingTaxonomy,
    isLoadingSections,
    isCreatingSection,
    isLoadingProperties,
    isLoadingPriceRec,
    errorMessage,
    loadListing,
    updateListing,
    fetchPriceRecommendation,
    fetchShopSections,
    createShopSection,
    fetchTaxonomyProperties,
    rescreenTrademark,
    generateSeo,
    buildPackage,
    restoreVersion,
    deleteVersion,
    deleteTagFromHistory,
    decideGate3,
    fetchTaxonomyCategories,
    updateTaxonomy,
  };
}

