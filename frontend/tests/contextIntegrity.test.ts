import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWorkflowContext } from "../composables/useWorkflowContext";
import { useListing } from "../composables/useListing";
import { useProduction } from "../composables/useProduction";
import { useArtworkVariants } from "../composables/useArtworkVariants";
import { useMockups } from "../composables/useMockups";

vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

describe("Context Integrity & Workflow Scoping (Phase A)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("useWorkflowContext", () => {
    it("fetches context and computes staleness state correctly", async () => {
      const mockContextResponse = {
        workflow_id: "wf-111",
        workflow_name: "Test Workflow",
        workflow_state: "PRODUCTION",
        workflow_version: 2,
        active_concept_id: "concept-1",
        active_concept_title: "Highland Cow Teacher",
        approved_artwork_asset_id: "art-1",
        production_master_asset_id: "master-1",
        active_mockup_count: 3,
        buyer_package_asset_id: "pkg-1",
        etsy_listing_id: "etsy-12345",
        hashes: {
          concept_context_hash: "chash123",
          artwork_context_hash: "ahash123",
          production_context_hash: "phash123",
          variant_set_hash: "vhash123",
          mockup_set_hash: "mhash123",
          listing_context_hash: "lhash123",
          etsy_sync_hash: "ehash123",
        },
        staleness: {
          concept_status: "CURRENT",
          artwork_status: "CURRENT",
          production_status: "CURRENT",
          variants_status: "CURRENT",
          mockups_status: "CURRENT",
          listing_status: "CURRENT",
          package_status: "CURRENT",
          etsy_sync_status: "CURRENT",
          is_any_stale: false,
          stale_reasons: [],
        },
      };

      vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockContextResponse));

      const {
        contextData,
        isStale,
        staleReasons,
        conceptStatus,
        fetchContext,
        resetState,
      } = useWorkflowContext();

      expect(contextData.value).toBeNull();
      expect(isStale.value).toBe(false);

      const result = await fetchContext("wf-111");
      expect(result).toBeDefined();
      expect(contextData.value?.workflow_id).toBe("wf-111");
      expect(isStale.value).toBe(false);
      expect(staleReasons.value).toEqual([]);
      expect(conceptStatus.value).toBe("CURRENT");

      // Test resetState
      resetState();
      expect(contextData.value).toBeNull();
    });

    it("detects stale listing copy when upstream concept changed", async () => {
      const mockStaleResponse = {
        workflow_id: "wf-111",
        workflow_name: "Test Workflow",
        workflow_state: "PRODUCTION",
        workflow_version: 3,
        active_concept_id: "concept-2",
        active_concept_title: "Sarcastic Skeleton",
        approved_artwork_asset_id: null,
        production_master_asset_id: null,
        active_mockup_count: 0,
        buyer_package_asset_id: null,
        etsy_listing_id: null,
        hashes: {
          concept_context_hash: "chash999",
          artwork_context_hash: "",
          production_context_hash: "",
          variant_set_hash: "",
          mockup_set_hash: "",
          listing_context_hash: "",
          etsy_sync_hash: "",
        },
        staleness: {
          concept_status: "CURRENT",
          artwork_status: "SUPERSEDED",
          production_status: "SUPERSEDED",
          variants_status: "SUPERSEDED",
          mockups_status: "SUPERSEDED",
          listing_status: "STALE",
          package_status: "SUPERSEDED",
          etsy_sync_status: "SUPERSEDED",
          is_any_stale: true,
          stale_reasons: ["Listing copy is based on superseded concept concept-1."],
        },
      };

      vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockStaleResponse));

      const { fetchContext, isStale, staleReasons, listingStatus } = useWorkflowContext();
      await fetchContext("wf-111");

      expect(isStale.value).toBe(true);
      expect(listingStatus.value).toBe("STALE");
      expect(staleReasons.value.length).toBe(1);
    });
  });

  describe("Composable State Isolation & Reset", () => {
    it("useListing resets state on workflow switch", async () => {
      const mockDraft = {
        id: "draft-1",
        workflow_id: "wf-A",
        title: "Highland Cow Shirt",
        description: "Cute shirt",
        tags: ["cow"],
      };

      vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockDraft));

      const { listingDraft, loadListing, resetState } = useListing();

      await loadListing("wf-A");
      expect(listingDraft.value?.workflow_id).toBe("wf-A");

      // Switching workflow resets previous state
      resetState();
      expect(listingDraft.value).toBeNull();
    });

    it("useProduction resets state on workflow switch", async () => {
      const mockJob = {
        id: "job-1",
        workflow_id: "wf-A",
        status: "SUCCEEDED",
        master_asset: { id: "asset-1", url: "http://example.com/master.png" },
      };

      vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockJob));

      const { latestProductionJob, loadProductionJob, resetState } = useProduction();

      await loadProductionJob("wf-A");
      expect(latestProductionJob.value?.id).toBe("job-1");

      resetState();
      expect(latestProductionJob.value).toBeNull();
    });

    it("useArtworkVariants resets state on workflow switch", async () => {
      const mockVariants = [
        {
          id: "var-1",
          workflow_id: "wf-A",
          variant_type: "white",
          variant_status: "approved",
        },
      ];

      vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockVariants));

      const { variants, fetchVariants, resetState } = useArtworkVariants();

      await fetchVariants("wf-A");
      expect(variants.value.length).toBe(1);

      resetState();
      expect(variants.value.length).toBe(0);
    });

    it("useMockups resets state on workflow switch", () => {
      const { localMockupAssets, syncMockupAssets, resetState } = useMockups();

      syncMockupAssets([
        {
          id: "mock-1",
          storage_key: "mock.jpg",
          provenance: { asset_type: "mockup", source: "user_template", template_id: "tmpl-1", product_type: "tshirt" },
        } as any,
      ]);
      expect(localMockupAssets.value.length).toBe(1);

      resetState();
      expect(localMockupAssets.value.length).toBe(0);
    });
  });
});
