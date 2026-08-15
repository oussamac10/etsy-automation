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
  operations: ["trim", "upscale", "typography", "qa", "mockup"],
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
  mockup_assets: [],
  mockup_urls: {
    tshirt: "http://localhost:9000/etsy/tshirt.png",
    sweatshirt: "http://localhost:9000/etsy/sweatshirt.png",
    tote: "http://localhost:9000/etsy/tote.png",
    mug: "http://localhost:9000/etsy/mug.png",
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
    expect(wrapper.text()).toContain("4500×5400 px");
    expect(wrapper.text()).toContain("300 DPI");
  });

  it("renders completed master file preview, QA report and mockups when production succeeds", async () => {
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
    expect(wrapper.text()).toContain("Master Print PNG");
    expect(wrapper.text()).toContain("Download Master PNG");
    expect(wrapper.text()).toContain("Automated QA Validation Report");
    expect(wrapper.text()).toContain("QA PASSED");
    expect(wrapper.text()).toContain("Product Mockup Gallery");
    expect(wrapper.text()).toContain("Regenerate Master & Mockups");
  });
});
