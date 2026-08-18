import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import WorkflowListingTab from "../components/workflow/listing/WorkflowListingTab.vue";
import ListingEditorCard from "../components/workflow/listing/ListingEditorCard.vue";
import TagEditorCard from "../components/workflow/listing/TagEditorCard.vue";
import IpRiskCard from "../components/workflow/listing/IpRiskCard.vue";
import CustomerPackageCard from "../components/workflow/listing/CustomerPackageCard.vue";
import { useListing } from "../composables/useListing";
import type { ListingDraft } from "../types/listing";

vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

const mockDraft: ListingDraft = {
  id: "draft-123",
  workflow_id: "wf-123",
  title: "Vintage Mushroom PNG Digital Download Sublimation Design",
  description: "High resolution 4500x5400 px digital PNG file for t-shirts.",
  tags: [
    "png download",
    "sublimation shirt",
    "vintage mushroom",
    "cottagecore art",
    "retro vibes",
    "digital print",
    "clipart file",
    "dtg ready",
    "shirt sublimation",
    "mug graphic",
    "transparent png",
    "commercial use",
    "instant download",
  ],
  price_minor_units: null,
  currency: "USD",
  ai_disclosure: "Artwork generated with AI assistance and hand-composited.",
  licence_text: "Commercial Use License",
  customer_instructions: "Download instructions",
  ip_reviewed_phrase: "vintage mushroom",
  ip_risk_level: "low",
  ip_findings: {
    searched_phrases: ["vintage mushroom"],
    match_count: 0,
    findings: [],
    disclaimer: "Preliminary automated trademark screening only — not legal advice.",
    requires_acknowledgement: false,
    blocks_approval: false,
  },
  ip_acknowledged_at: null,
  ip_acknowledged_by: null,
  version: 1,
  created_at: "2026-08-18T10:00:00Z",
  updated_at: "2026-08-18T10:00:00Z",
  package_asset: {
    id: "asset-zip-1",
    workflow_id: "wf-123",
    storage_key: "workflows/wf-123/packages/customer-package-v1.zip",
    mime_type: "application/zip",
    byte_size: 15728640,
    checksum_sha256: "abc123def456sha256",
    width: null,
    height: null,
    has_alpha: null,
    has_transparent_pixels: null,
    provenance: { kind: "customer_package" },
    created_at: "2026-08-18T10:00:00Z",
  },
  package_download_url: "http://localhost:8000/signed/customer-package-v1.zip",
};

describe("useListing Composable", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches listing draft successfully", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockDraft);
    vi.stubGlobal("$fetch", fetchMock);

    const { listingDraft, loadListing, isLoading } = useListing();
    expect(listingDraft.value).toBeNull();

    const promise = loadListing("wf-123");
    expect(isLoading.value).toBe(true);

    const result = await promise;
    expect(isLoading.value).toBe(false);
    expect(result).toEqual(mockDraft);
    expect(listingDraft.value).toEqual(mockDraft);
  });

  it("updates listing draft with optimistic locking payload", async () => {
    const updatedDraft = { ...mockDraft, version: 2, title: "New Title" };
    const fetchMock = vi.fn().mockResolvedValue(updatedDraft);
    vi.stubGlobal("$fetch", fetchMock);

    const { updateListing, listingDraft } = useListing();
    const result = await updateListing("wf-123", {
      title: "New Title",
      description: mockDraft.description,
      tags: mockDraft.tags,
      expected_version: 1,
    });

    expect(result).toEqual(updatedDraft);
    expect(listingDraft.value).toEqual(updatedDraft);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workflows/wf-123/listing",
      expect.objectContaining({
        method: "PUT",
        body: expect.objectContaining({ title: "New Title", expected_version: 1 }),
      })
    );
  });

  it("triggers trademark re-screening", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockDraft);
    vi.stubGlobal("$fetch", fetchMock);

    const { rescreenTrademark } = useListing();
    await rescreenTrademark("wf-123");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workflows/wf-123/listing/rescreen",
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("WorkflowListingTab UI Components", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockDraft));
  });

  it("renders listing editor, tags, IP risk, and customer package", async () => {
    const wrapper = mount(WorkflowListingTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "LISTING_REVIEW",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    await flushPromises();

    expect(wrapper.findComponent(ListingEditorCard).exists()).toBe(true);
    expect(wrapper.findComponent(TagEditorCard).exists()).toBe(true);
    expect(wrapper.findComponent(IpRiskCard).exists()).toBe(true);
    expect(wrapper.findComponent(CustomerPackageCard).exists()).toBe(true);

    // Verify tag count rendered
    expect(wrapper.text()).toContain("13 / 13 tags");
    // Verify risk cleared
    expect(wrapper.text()).toContain("Cleared");
    // Verify disclaimer
    expect(wrapper.text()).toContain("not legal advice");
    // Verify Gate 3 decision bar
    expect(wrapper.text()).toContain("Gate 3: Listing & IP Approval");
  });

  it("renders high risk blocked state correctly", async () => {
    const highRiskDraft: ListingDraft = {
      ...mockDraft,
      ip_risk_level: "high",
      ip_findings: {
        searched_phrases: ["disney castle"],
        match_count: 1,
        findings: [{ is_live: true, match_type: "EXACT_LIVE_POD_OVERLAP" }],
        disclaimer: "Preliminary automated trademark screening only — not legal advice.",
        requires_acknowledgement: false,
        blocks_approval: true,
      },
    };

    vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(highRiskDraft));

    const wrapper = mount(WorkflowListingTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "LISTING_REVIEW",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("High Risk");
    expect(wrapper.text()).toContain("Approval Blocked");
  });
});
