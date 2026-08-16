import { ref, computed, watch } from "vue";
import type { MockupAsset, MockupTemplateItem } from "~/types/mockup";
import { normalizeProductKey, extractProductFromKey } from "~/utils/mockupProducts";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";

export function useMockups(
  activeMasterAssetId?: () => string | null | undefined,
  intendedProducts?: () => string[] | undefined,
) {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

  const localMockupAssets = ref<MockupAsset[]>([]);
  const templates = ref<MockupTemplateItem[]>([]);
  const isLoadingTemplates = ref(false);
  const selectedMockupTab = ref<string>("tshirt");

  function syncMockupAssets(assets: any[]) {
    localMockupAssets.value = assets ? [...assets] : [];
  }

  // Authoritative grouping of valid user-template mockups
  const mockupsByProduct = computed<Record<string, MockupAsset[]>>(() => {
    const map: Record<string, MockupAsset[]> = {};
    const currentMasterId = activeMasterAssetId ? activeMasterAssetId() : null;

    for (const a of localMockupAssets.value) {
      const prov = a.provenance;
      // Strict user-template validation
      if (!prov) continue;
      const isValidUserMockup =
        prov.asset_type === "mockup" &&
        prov.source === "user_template" &&
        Boolean(prov.template_id);
      if (!isValidUserMockup) continue;

      if (
        currentMasterId &&
        a.derived_from_id &&
        a.derived_from_id !== currentMasterId &&
        prov.source_asset_id &&
        prov.source_asset_id !== currentMasterId
      ) {
        continue;
      }
      const p = normalizeProductKey(prov.product_type || extractProductFromKey(a.storage_key));
      if (!map[p]) map[p] = [];
      map[p].push(a);
    }

    for (const k in map) {
      map[k].sort((a, b) => {
        const aOrd = Number(a.provenance?.listing_order ?? 999);
        const bOrd = Number(b.provenance?.listing_order ?? 999);
        if (aOrd !== bOrd) return aOrd - bOrd;
        const aCov = a.provenance?.is_cover ? 0 : 1;
        const bCov = b.provenance?.is_cover ? 0 : 1;
        if (aCov !== bCov) return aCov - bCov;
        const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
        const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
        return bTime - aTime;
      });
    }

    return map;
  });

  const availableProductTabs = computed<string[]>(() => {
    const intended = (intendedProducts ? intendedProducts() || [] : [])
      .map((p) => normalizeProductKey(p))
      .filter(Boolean);
    const activeWithMockups = Object.keys(mockupsByProduct.value).filter(
      (k) => (mockupsByProduct.value[k] || []).length > 0
    );
    const combined = Array.from(new Set([...intended, ...activeWithMockups]));
    return combined;
  });

  watch(
    [availableProductTabs, mockupsByProduct],
    ([tabs, map]) => {
      if (tabs.length === 0) return;
      const currentCount = (map[selectedMockupTab.value] || []).length;
      if (currentCount === 0) {
        const firstWithMockup = tabs.find((t) => (map[t] || []).length > 0);
        if (firstWithMockup) {
          selectedMockupTab.value = firstWithMockup;
          return;
        }
      }
      if (!tabs.includes(selectedMockupTab.value)) {
        selectedMockupTab.value = tabs[0];
      }
    },
    { immediate: true }
  );

  const currentTabMockups = computed<MockupAsset[]>(() => {
    return mockupsByProduct.value[selectedMockupTab.value] || [];
  });

  async function loadTemplates(productType?: string): Promise<MockupTemplateItem[]> {
    isLoadingTemplates.value = true;
    try {
      const q = productType ? `?product_type=${productType}` : "";
      const res = await $fetch<MockupTemplateItem[]>(
        `${apiBase}/api/v1/mockup-templates${q}`,
        {
          headers: { Accept: "application/json" },
          credentials: "include",
        }
      );
      templates.value = res || [];
      return templates.value;
    } catch {
      templates.value = [];
      return [];
    } finally {
      isLoadingTemplates.value = false;
    }
  }

  async function deleteMockup(workflowId: string, assetId: string): Promise<boolean> {
    if (!workflowId || !assetId) return false;
    try {
      await $fetch(`${apiBase}/api/v1/workflows/${workflowId}/mockups/${assetId}`, {
        method: "DELETE",
        headers: getCsrfHeaders(),
        credentials: "include",
      });
      localMockupAssets.value = localMockupAssets.value.filter((a) => a.id !== assetId);
      return true;
    } catch (err: unknown) {
      throw new Error(getApiErrorMessage(err, "Failed to delete mockup."));
    }
  }

  async function deleteTemplate(templateId: string): Promise<boolean> {
    if (!templateId) return false;
    try {
      await $fetch(`${apiBase}/api/v1/mockup-templates/${templateId}`, {
        method: "DELETE",
        headers: getCsrfHeaders(),
        credentials: "include",
      });
      templates.value = templates.value.filter((t) => t.id !== templateId);
      return true;
    } catch (err: unknown) {
      throw new Error(getApiErrorMessage(err, "Failed to delete template."));
    }
  }

  return {
    localMockupAssets,
    templates,
    isLoadingTemplates,
    selectedMockupTab,
    mockupsByProduct,
    availableProductTabs,
    currentTabMockups,
    syncMockupAssets,
    loadTemplates,
    deleteMockup,
    deleteTemplate,
  };
}
