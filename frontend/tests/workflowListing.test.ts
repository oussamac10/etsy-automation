import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import WorkflowListingTab from "../components/workflow/listing/WorkflowListingTab.vue";
import WorkflowEtsyTab from "../components/workflow/listing/WorkflowEtsyTab.vue";
import ListingEditorCard from "../components/workflow/listing/ListingEditorCard.vue";
import TagEditorCard from "../components/workflow/listing/TagEditorCard.vue";
import IpRiskCard from "../components/workflow/listing/IpRiskCard.vue";
import CustomerPackageCard from "../components/workflow/listing/CustomerPackageCard.vue";
import CategorySelectorCard from "../components/workflow/listing/CategorySelectorCard.vue";
import TaxonomyAttributesCard from "../components/workflow/listing/TaxonomyAttributesCard.vue";
import PricingInventoryCard from "../components/workflow/listing/PricingInventoryCard.vue";
import ShopOrganizationCard from "../components/workflow/listing/ShopOrganizationCard.vue";
import EtsyDraftCard from "../components/workflow/listing/EtsyDraftCard.vue";
import WorkflowStageNav from "../components/workflow/WorkflowStageNav.vue";
import { useListing } from "../composables/useListing";
import type { ListingDraft } from "../types/listing";

vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

vi.stubGlobal("useRoute", () => ({
  query: {},
  params: { id: "wf-123" },
}));

vi.stubGlobal("useRouter", () => ({
  replace: vi.fn(),
  push: vi.fn(),
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
  price_minor_units: 499,
  currency: "USD",
  taxonomy_id: 6844,
  taxonomy_path: "Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
  sku: "NCP-MUSHROOM-123",
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

describe("WorkflowListingTab 5 Sub-Tabs Navigation & Structure", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockDraft));
  });

  it("renders 5 sub-tab buttons and defaults to Listing Content sub-tab", async () => {
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

    // Verify 5 sub-tabs exist in navigation
    const tabs = wrapper.findAll('[role="tab"]');
    expect(tabs.length).toBe(5);
    expect(tabs[0].text()).toContain("Listing Content");
    expect(tabs[1].text()).toContain("Etsy Details");
    expect(tabs[2].text()).toContain("IP & Compliance");
    expect(tabs[3].text()).toContain("Buyer Delivery");
    expect(tabs[4].text()).toContain("Final Review");

    // Default sub-tab: Listing Content
    expect(wrapper.find('[data-testid="subtab-content"]').exists()).toBe(true);
    expect(wrapper.findComponent(ListingEditorCard).exists()).toBe(true);
    expect(wrapper.findComponent(TagEditorCard).exists()).toBe(true);

    // Gate 3 decision bar should NOT be on Listing Content sub-tab
    expect(wrapper.text()).not.toContain("Gate 3: Listing & IP Approval");
  });

  it("navigates to Etsy Details sub-tab and renders classification components", async () => {
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

    const etsyDetailsBtn = wrapper.findAll('[role="tab"]')[1];
    await etsyDetailsBtn.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="subtab-etsy-details"]').exists()).toBe(true);
    expect(wrapper.findComponent(CategorySelectorCard).exists()).toBe(true);
    expect(wrapper.findComponent(TaxonomyAttributesCard).exists()).toBe(true);
    expect(wrapper.findComponent(PricingInventoryCard).exists()).toBe(true);
    expect(wrapper.findComponent(ShopOrganizationCard).exists()).toBe(true);

    // Gate 3 decision bar should NOT be on Etsy Details sub-tab
    expect(wrapper.text()).not.toContain("Gate 3: Listing & IP Approval");
  });

  it("navigates to IP & Compliance and Buyer Delivery sub-tabs", async () => {
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

    // IP & Compliance
    const ipBtn = wrapper.findAll('[role="tab"]')[2];
    await ipBtn.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="subtab-ip-compliance"]').exists()).toBe(true);
    expect(wrapper.findComponent(IpRiskCard).exists()).toBe(true);

    // Buyer Delivery
    const deliveryBtn = wrapper.findAll('[role="tab"]')[3];
    await deliveryBtn.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="subtab-delivery"]').exists()).toBe(true);
    expect(wrapper.findComponent(CustomerPackageCard).exists()).toBe(true);
  });

  it("navigates to Final Review, summarizes all sections, and displays Gate 3 approval controls", async () => {
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

    // Final Review
    const finalReviewBtn = wrapper.findAll('[role="tab"]')[4];
    await finalReviewBtn.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="subtab-final-review"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("Ready for Etsy?");
    expect(wrapper.text()).toContain("Listing Content");
    expect(wrapper.text()).toContain("Etsy Details");
    expect(wrapper.text()).toContain("IP & Compliance");
    expect(wrapper.text()).toContain("Buyer Delivery");

    // Gate 3 decision bar MUST be in Final Review
    expect(wrapper.text()).toContain("Gate 3: Listing & IP Approval");
    expect(wrapper.text()).toContain("Approve for Etsy Draft");
  });

  it("renders high risk blocked state correctly in Final Review", async () => {
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

    // Switch to Final Review
    const finalReviewBtn = wrapper.findAll('[role="tab"]')[4];
    await finalReviewBtn.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("HIGH RISK");
    expect(wrapper.text()).toContain("Approval Blocked");
  });

  it("confirms Etsy draft creation is only in Step 5 (WorkflowEtsyTab), not in Step 4", async () => {
    const listingWrapper = mount(WorkflowListingTab, {
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
    // Step 4 must NOT contain EtsyDraftCard
    expect(listingWrapper.findComponent(EtsyDraftCard).exists()).toBe(false);

    // Step 5 (WorkflowEtsyTab) MUST contain EtsyDraftCard
    const etsyWrapper = mount(WorkflowEtsyTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "READY_FOR_ETSY_DRAFT",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    await flushPromises();
    expect(etsyWrapper.findComponent(EtsyDraftCard).exists()).toBe(true);
  });

  it("hides '5. Etsy Dispatch' tab in WorkflowStageNav until Gate 3 is approved, then shows it", async () => {
    // 1. In LISTING_REVIEW: 5. Etsy Dispatch tab MUST be hidden
    const unapprovedNav = mount(WorkflowStageNav, {
      props: {
        activeTab: "listing",
        workflowState: "LISTING_REVIEW",
        conceptsCount: 3,
        candidatesCount: 4,
        productionStatus: "SUCCEEDED",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    expect(unapprovedNav.text()).toContain("4. Listing & IP Review");
    expect(unapprovedNav.text()).not.toContain("5. Etsy Dispatch");
    expect(unapprovedNav.text()).not.toContain("5. Etsy");

    // 2. In READY_FOR_ETSY_DRAFT (Gate 3 approved): 5. Etsy Dispatch tab MUST be visible
    const approvedNav = mount(WorkflowStageNav, {
      props: {
        activeTab: "etsy",
        workflowState: "READY_FOR_ETSY_DRAFT",
        conceptsCount: 3,
        candidatesCount: 4,
        productionStatus: "SUCCEEDED",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    expect(approvedNav.text()).toContain("5. Etsy Dispatch");
  });

  it("emits approved event on Gate 3 approval to trigger redirect to Etsy Dispatch tab", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url.includes("/approvals")) {
        return Promise.resolve({
          ...mockDraft,
          workflow_state: "READY_FOR_ETSY_DRAFT",
        });
      }
      return Promise.resolve(mockDraft);
    });
    vi.stubGlobal("$fetch", fetchMock);

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

    // Switch to Final Review sub-tab
    const finalReviewBtn = wrapper.findAll('[role="tab"]')[4];
    await finalReviewBtn.trigger("click");
    await flushPromises();

    // Find and click Approve button
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Approve for Etsy Draft"));
    expect(approveBtn).toBeDefined();
    await approveBtn!.trigger("click");
    await flushPromises();

    // Verify approved event was emitted
    expect(wrapper.emitted("approved")).toBeTruthy();
  });
});

describe("TaxonomyAttributesCard AI & Smart Suggestions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockTaxonomyProps = [
    {
      property_id: 82731,
      name: "Craft type",
      is_required: true,
      is_multivalued: true,
      possible_values: [
        { value_id: 441908, name: "Sublimation" },
        { value_id: 441909, name: "Card making" },
      ],
      suggested_value_ids: [441908],
      suggested_values: ["Sublimation"],
    },
    {
      property_id: 82732,
      name: "Holiday",
      is_required: false,
      is_multivalued: false,
      possible_values: [
        { value_id: 551201, name: "Christmas" },
        { value_id: 551202, name: "Halloween" },
      ],
      suggested_value_ids: [551201],
      suggested_values: ["Christmas"],
    },
  ];

  it("loads properties on mount without making any AI endpoint calls", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("taxonomy-properties/ai-suggest")) {
        throw new Error("AI endpoint must not be called automatically on mount!");
      }
      if (url.includes("taxonomy-properties")) {
        return Promise.resolve(mockTaxonomyProps);
      }
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(TaxonomyAttributesCard, {
      props: {
        workflowId: "wf-123",
        taxonomyId: 6844,
        etsyProperties: {},
      },
      global: {
        stubs: { Icon: { template: "<i />" } },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Category Attributes");
    expect(wrapper.text()).toContain("Craft type");
    expect(wrapper.text()).toContain("Holiday");
    // Verify AI endpoint was NEVER called
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("taxonomy-properties/ai-suggest"),
      expect.anything()
    );
  });

  it("triggers AI suggest endpoint only when user explicitly clicks the AI button", async () => {
    const mockAiResponse = {
      workflow_id: "wf-123",
      taxonomy_id: 6844,
      suggestions: [
        {
          property_id: 82731,
          property_name: "Craft type",
          value_ids: [441908],
          values: ["Sublimation"],
          confidence: 0.96,
          reason: "Explicitly targets sublimation design files.",
          is_required: true,
          is_multivalued: true,
          is_high_confidence: true,
        },
      ],
      high_confidence_count: 1,
      fingerprint: "abc123fp",
      cached: false,
    };

    const fetchMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url.includes("taxonomy-properties/ai-suggest")) {
        return Promise.resolve(mockAiResponse);
      }
      if (url.includes("taxonomy-properties")) {
        return Promise.resolve(mockTaxonomyProps);
      }
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(TaxonomyAttributesCard, {
      props: {
        workflowId: "wf-123",
        taxonomyId: 6844,
        etsyProperties: {},
      },
      global: {
        stubs: { Icon: { template: "<i />" } },
      },
    });

    await flushPromises();

    // Click "AI Suggest Attributes" button
    const aiBtn = wrapper.findAll("button").find((b) => b.text().includes("AI Suggest Attributes"));
    expect(aiBtn).toBeDefined();
    await aiBtn!.trigger("click");
    await flushPromises();

    // Verify AI endpoint was called
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("taxonomy-properties/ai-suggest"),
      expect.objectContaining({ method: "POST" })
    );

    // Verify suggestions are displayed in UI
    expect(wrapper.text()).toContain("AI suggestions ready for this campaign");
    expect(wrapper.text()).toContain("96% AI High");
    expect(wrapper.text()).toContain("Explicitly targets sublimation design files.");

    // Apply High-Confidence
    const applyHighBtn = wrapper.findAll("button").find((b) => b.text().includes("Apply 1 High-Confidence"));
    expect(applyHighBtn).toBeDefined();
    await applyHighBtn!.trigger("click");
    await flushPromises();

    // Emits local update
    expect(wrapper.emitted("update:etsyProperties")).toBeTruthy();
  });
});

