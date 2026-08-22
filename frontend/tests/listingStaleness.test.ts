import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import WorkflowListingTab from "../components/workflow/listing/WorkflowListingTab.vue";
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

const mockStaleDraft: ListingDraft = {
  id: "draft-123",
  workflow_id: "wf-123",
  title: "Sarcastic Bookworm Skeleton PNG",
  description: "Cozy skeleton reading a book with iced coffee illustration",
  tags: ["skeleton png", "book lover"],
  price_minor_units: 499,
  currency: "USD",
  taxonomy_id: 6844,
  taxonomy_path: "Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
  sku: "NCP-SKELETON-123",
  version: 1,
  ip_risk_level: "low",
  ip_findings: { findings: [] } as any,
  is_stale: true,
  stale_reason: "Listing copy was generated for a different concept (Sarcastic Bookworm Skeleton). Current active concept is Highland Cow Teacher Back to School Calf.",
  concept_id: "c-old-123",
  concept_version: 1,
  listing_context_hash: "oldhash123",
};

describe("Listing Staleness Detection & Banner", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

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
    expect(banner.text()).toContain("Highland Cow Teacher");
    expect(banner.text()).toContain("Regenerate Listing Copy");
  });

  it("triggers generateSeo('all') when Regenerate Listing Copy button is clicked", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url.includes("/listing/generate-seo")) {
        return Promise.resolve({
          ...mockStaleDraft,
          title: "Highland Cow Teacher Back to School Calf PNG",
          description: "Cute highland cow teacher illustration",
          tags: ["highland cow png", "teacher clipart"],
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
