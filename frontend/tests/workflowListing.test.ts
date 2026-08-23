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

  it("renders Gate 2 pending warning and hides listing forms when artwork is not yet approved", async () => {
    const wrapper = mount(WorkflowListingTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "ART_REVIEW",
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
          NuxtLink: { template: "<a><slot /></a>" },
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="listing-gate2-pending-warning"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("Artwork Selection Required");
    expect(wrapper.text()).not.toContain("Gate 2");
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false);
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

    // Listing approval decision bar MUST be in Final Review
    expect(wrapper.text()).toContain("Listing & IP Approval");
    expect(wrapper.text()).not.toContain("Gate 3");
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
    expect(unapprovedNav.text()).not.toContain("5. Etsy Draft");
    expect(unapprovedNav.text()).not.toContain("5. Etsy");

    // 2. In READY_FOR_ETSY_DRAFT (Listing approved): 5. Etsy Draft tab MUST be visible
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

    expect(approvedNav.text()).toContain("5. Etsy Draft");
  });

  it("emits approved event on listing approval to trigger redirect to Etsy Draft tab", async () => {
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

describe("TaxonomyAttributesCard Manual Selection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockTaxonomyProps = [
    {
      property_id: 82731,
      name: "Craft type",
      is_required: true,
      supports_attributes: true,
      is_multivalued: true,
      possible_values: [
        { value_id: 441908, name: "Sublimation" },
        { value_id: 441909, name: "Printing & printmaking" },
      ],
    },
    {
      property_id: 99881,
      name: "Holiday",
      is_required: false,
      supports_attributes: true,
      is_multivalued: false,
      possible_values: [
        { value_id: 551201, name: "Christmas" },
        { value_id: 551202, name: "Halloween" },
      ],
    },
  ];

  it("loads properties on mount without auto-selection, no AI buttons, and no Smart Suggest", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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
    expect(wrapper.text()).toContain("0 selected");
    expect(wrapper.text()).toContain("Craft type");
    expect(wrapper.text()).toContain("* Required");
    expect(wrapper.text()).toContain("Required selection missing");
    expect(wrapper.text()).toContain("Holiday");
    expect(wrapper.text()).toContain("Optional");

    // Proves NO AI buttons or Smart Suggest buttons exist
    const buttonsText = wrapper.findAll("button").map((b) => b.text());
    expect(buttonsText.some((t) => t.includes("AI Suggest"))).toBe(false);
    expect(buttonsText.some((t) => t.includes("Smart Suggest"))).toBe(false);
    expect(buttonsText.some((t) => t.includes("AI Available"))).toBe(false);
  });

  it("supports manual selection of multivalued chips and single-valued dropdowns", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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

    // Click Sublimation chip
    const subChip = wrapper.findAll("button").find((b) => b.text().includes("Sublimation"));
    expect(subChip).toBeDefined();
    await subChip!.trigger("click");
    await flushPromises();

    // Emits update:etsyProperties with manual selection
    const emitted = wrapper.emitted("update:etsyProperties");
    expect(emitted).toBeTruthy();
    expect(emitted![0][0]).toMatchObject({
      "82731": {
        property_id: 82731,
        values: ["Sublimation"],
        value_ids: [441908],
      },
    });
  });

  it("Clear Optional clears unrequired properties and retains required selections", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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
        etsyProperties: {
          "82731": { property_id: 82731, value_ids: [441908], values: ["Sublimation"] },
          "99881": { property_id: 99881, value_ids: [551201], values: ["Christmas"] },
        },
      },
      global: {
        stubs: { Icon: { template: "<i />" } },
      },
    });

    await flushPromises();
    expect(wrapper.text()).toContain("2 selected");

    const clearBtn = wrapper.findAll("button").find((b) => b.text().includes("Clear Optional"));
    expect(clearBtn).toBeDefined();
    await clearBtn!.trigger("click");
    await flushPromises();

    const emitted = wrapper.emitted("update:etsyProperties");
    expect(emitted).toBeTruthy();
    const updated = emitted![emitted!.length - 1][0] as Record<string, any>;
    // Required 82731 retained
    expect(updated["82731"]).toBeDefined();
    // Optional 99881 cleared
    expect(updated["99881"]).toBeUndefined();
  });

  it("displays mismatch warning banner and emits reviewCategory when requested", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("taxonomy-properties")) {
        return Promise.resolve(mockTaxonomyProps);
      }
      if (url.includes("fitness")) {
        return Promise.resolve({
          taxonomy_id: 6844,
          taxonomy_path: "Craft Supplies & Tools > Clip Art",
          fit_score: 0.35,
          fit_reasons: [],
          warnings: ["Required Craft type values are limited to paper/collage uses and do not match apparel/sublimation intent."],
          has_mismatched_required_attributes: true,
          mismatched_required_reason: "Craft type is required, but Etsy only offers paper/collage-related values for this category.",
        });
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

    expect(wrapper.text()).toContain("Category mismatch");
    expect(wrapper.text()).toContain("Craft type is required, but Etsy only offers paper/collage-related values");
    expect(wrapper.text()).toContain("Review Etsy Category");

    const reviewBtn = wrapper.findAll("button").find((b) => b.text().includes("Review Etsy Category"));
    expect(reviewBtn).toBeDefined();
    await reviewBtn!.trigger("click");

    expect(wrapper.emitted("reviewCategory")).toBeTruthy();
  });

  it("Gate 3 displays category mismatch reason and blocks approval when category attributes mismatch", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("fitness")) {
        return Promise.resolve({
          taxonomy_id: 6844,
          taxonomy_path: "Craft Supplies & Tools > Canvas & Surfaces > Clip Art & Image Files",
          fit_score: 0.28,
          fit_level: "poor",
          blocking_mismatch: true,
          has_mismatched_required_attributes: true,
          mismatched_required_reason: "Craft type is required, but Etsy only offers paper/collage-related values for this category.",
          fit_reasons: [],
          warnings: ["Required Craft type values are limited to paper/collage uses."],
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

    // Navigate to Final Review
    const finalReviewBtn = wrapper.findAll('[role="tab"]')[4];
    await finalReviewBtn.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Selected Etsy category does not match this campaign's intended use.");
  });
});

describe("Listing Staleness Detection & Banner", () => {
  const mockStaleDraft: ListingDraft = {
    ...mockDraft,
    id: "draft-stale-123",
    title: "Sarcastic Bookworm Skeleton PNG",
    is_stale: true,
    stale_reason: "Listing copy was generated for a different concept. Current active concept is Highland Cow Teacher Back to School Calf.",
    concept_id: "c-old-123",
    concept_version: 1,
    listing_context_hash: "oldhash123",
  };

  it("renders the stale listing warning banner when is_stale is true", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/listing")) {
        return Promise.resolve(mockStaleDraft);
      }
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(WorkflowListingTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "LISTING_REVIEW",
      },
      global: {
        stubs: {
          Icon: { template: '<span class="mock-icon" />' },
          Badge: { template: '<span><slot /></span>' },
          Button: { template: '<button><slot /></button>' },
          NuxtLink: { template: '<a><slot /></a>' },
          ListingEditorCard: true,
          TagEditorCard: true,
          IpRiskCard: true,
          CustomerPackageCard: true,
          WorkflowStageNav: true,
        },
      },
    });

    await flushPromises();

    const banner = wrapper.find('[data-testid="listing-stale-banner"]');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain("Listing Copy Stale");
    expect(banner.text()).toContain("Regenerate Listing Copy");
  });

  it("triggers generateSeo('all') when Regenerate Listing Copy button is clicked", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/listing/generate-seo")) {
        return Promise.resolve({
          ...mockStaleDraft,
          title: "Highland Cow Teacher Back to School Calf PNG",
          is_stale: false,
          stale_reason: null,
        });
      }
      if (url.includes("/listing")) {
        return Promise.resolve(mockStaleDraft);
      }
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(WorkflowListingTab, {
      props: {
        workflowId: "wf-123",
        workflowState: "LISTING_REVIEW",
      },
      global: {
        stubs: {
          Icon: { template: '<span class="mock-icon" />' },
          Badge: { template: '<span><slot /></span>' },
          Button: {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          NuxtLink: { template: '<a><slot /></a>' },
          ListingEditorCard: true,
          TagEditorCard: true,
          IpRiskCard: true,
          CustomerPackageCard: true,
          WorkflowStageNav: true,
        },
      },
    });

    await flushPromises();

    const regenBtn = wrapper.find('[data-testid="listing-stale-banner"] button');
    expect(regenBtn.exists()).toBe(true);
    await regenBtn.trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workflows/wf-123/listing/generate-seo?target=all",
      expect.objectContaining({ method: "POST" })
    );
  });
});





