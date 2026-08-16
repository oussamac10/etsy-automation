import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import workflowPage from "../pages/workflow/[id].vue";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: {
      id: "wf-prod-123",
    },
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

const NavBarMock = {
  template: "<div>NavBar Mock</div>",
};

const NuxtLinkMock = {
  template: "<a><slot /></a>",
};

const mockApprovedWorkflow = {
  id: "wf-prod-123",
  owner_id: "user-123",
  idea_mode: "market-led",
  name: "Production Pipeline Workflow",
  target_marketplace: "etsy",
  target_country: "US",
  output_language: "en",
  target_buyer: "minimalists",
  intended_product_uses: ["tshirt", "mug"],
  state: "ARTWORK_APPROVED",
  version: 3,
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
};

const mockProductionSucceededJob = {
  id: "prod-job-1",
  workflow_id: "wf-prod-123",
  source_asset_id: "source-asset-1",
  output_asset_id: "master-asset-1",
  operations: ["trim", "upscale", "typography", "qa"],
  status: "SUCCEEDED",
  idempotency_key: "production:wf-prod-123:abc",
  attempt_count: 1,
  qa_report: {
    dimensions_valid: true,
    width: 4500,
    height: 5400,
    density_dpi: 300,
    has_alpha: true,
    has_transparent_pixels: true,
    transparent_background_valid: true,
    safe_margins_valid: true,
    cropped_edges_detected: false,
    color_space: "sRGB",
    file_size_bytes: 4500000,
    checksum_sha256: "sha256master123456",
    typography_applied: true,
    exact_slogan_recorded: "STAY GOLDEN",
    warnings: [],
    qa_passed: true,
  },
  qa_passed: true,
  started_at: "2026-08-15T12:01:00Z",
  completed_at: "2026-08-15T12:02:00Z",
  failure_kind: null,
  failure_message: null,
  created_at: "2026-08-15T12:00:30Z",
  master_asset: {
    id: "master-asset-1",
    workflow_id: "wf-prod-123",
    artwork_job_id: null,
    derived_from_id: "source-asset-1",
    storage_key: "production/wf-prod-123/master.png",
    mime_type: "image/png",
    byte_size: 4500000,
    checksum_sha256: "sha256master123456",
    width: 4500,
    height: 5400,
    has_alpha: true,
    has_transparent_pixels: true,
    provenance: { profile: "etsy-png-standard" },
    created_at: "2026-08-15T12:02:00Z",
    url: "http://localhost:9000/etsy/master.png",
  },
  mockup_assets: [
    {
      id: "mockup-1",
      workflow_id: "wf-prod-123",
      storage_key: "production/wf-prod-123/mockups/custom_tshirt_mockup1.jpg",
      mime_type: "image/jpeg",
      byte_size: 150000,
      checksum_sha256: "sha256mockup1",
      width: 1200,
      height: 1200,
      has_alpha: false,
      url: "http://localhost:9000/etsy/tshirt1.jpg",
      provenance: {
        asset_type: "mockup",
        product_type: "tshirt",
        template_name: "Black Bella Canvas Flatlay",
        is_cover: true,
        listing_order: 1,
      },
    },
    {
      id: "mockup-2",
      workflow_id: "wf-prod-123",
      storage_key: "production/wf-prod-123/mockups/custom_tshirt_mockup2.jpg",
      mime_type: "image/jpeg",
      byte_size: 150000,
      checksum_sha256: "sha256mockup2",
      width: 1200,
      height: 1200,
      has_alpha: false,
      url: "http://localhost:9000/etsy/tshirt2.jpg",
      provenance: {
        asset_type: "mockup",
        product_type: "tshirt",
        template_name: "White Bella Canvas Flatlay",
        is_cover: false,
        listing_order: 2,
      },
    },
    {
      id: "mockup-3",
      workflow_id: "wf-prod-123",
      storage_key: "production/wf-prod-123/mockups/custom_mug_mockup3.jpg",
      mime_type: "image/jpeg",
      byte_size: 150000,
      checksum_sha256: "sha256mockup3",
      width: 1200,
      height: 1200,
      has_alpha: false,
      url: "http://localhost:9000/etsy/mug3.jpg",
      provenance: {
        asset_type: "mockup",
        product_type: "mug",
        template_name: "Kitchen Scene Mug",
        is_cover: false,
        listing_order: 3,
      },
    },
  ],
  mockup_urls: {
    tshirt: "http://localhost:9000/etsy/tshirt1.jpg",
    mug: "http://localhost:9000/etsy/mug3.jpg",
  },
};

describe("Workflow Detail - Phase 7 Production Pipeline", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("renders ready state with Start PNG Production button when ARTWORK_APPROVED", async () => {
    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(null);
      if (url.includes("/api/v1/workflows/wf-prod-123")) return Promise.resolve(mockApprovedWorkflow);
      return Promise.resolve(null);
    }));

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Phase 7: Print-Ready PNG Production");
    expect(wrapper.text()).toContain("Start PNG Production");
  });

  it("renders completed master file preview, QA report and multi-mockup gallery when production succeeds", async () => {
    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(mockProductionSucceededJob);
      if (url.includes("/api/v1/workflows/wf-prod-123")) return Promise.resolve(mockApprovedWorkflow);
      return Promise.resolve(null);
    }));

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Production Complete");
    expect(wrapper.text()).toContain("Master PNG");
    expect(wrapper.text()).toContain("Download Master PNG");
    expect(wrapper.text()).toContain("Product Mockup Gallery");
    expect(wrapper.text()).toContain("3 listing mockups");
    expect(wrapper.text()).toContain("Black Bella Canvas Flatlay");
    expect(wrapper.text()).toContain("White Bella Canvas Flatlay");
    expect(wrapper.text()).toContain("Cover Image");
    expect(wrapper.text()).toContain("Add T-Shirt Mockup");
    expect(wrapper.text()).toContain("Regenerate Master PNG");
  });
});
