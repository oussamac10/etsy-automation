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
        source: "user_template",
        template_id: "tpl-tshirt-1",
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
        source: "user_template",
        template_id: "tpl-tshirt-2",
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
        source: "user_template",
        template_id: "tpl-mug-1",
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
    expect(wrapper.text()).toContain("Product Mockups");
    expect(wrapper.text()).toContain("3 listing mockups");
    expect(wrapper.text()).toContain("Black Bella Canvas Flatlay");
    expect(wrapper.text()).toContain("White Bella Canvas Flatlay");
    expect(wrapper.text()).toContain("Cover Image");
    expect(wrapper.text()).toContain("Add Another T-Shirt");
  });

  it("immediately updates T-shirt and Mug mockup preview URLs when switching candidate PNG without browser reload", async () => {
    let currentProdJob = { ...mockProductionSucceededJob };

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(currentProdJob);
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

    // Verify initial production A mockups
    const initialImgs = wrapper.findAll("img");
    const initialTshirtSrc = initialImgs.find((img) => img.attributes("src")?.includes("tshirt1.jpg"));
    expect(initialTshirtSrc).toBeDefined();

    // Simulate switching to Candidate B and production succeeding
    const updatedProdJob = {
      ...mockProductionSucceededJob,
      id: "prod-job-2",
      source_asset_id: "source-asset-2",
      output_asset_id: "master-asset-2",
      master_asset: {
        ...mockProductionSucceededJob.master_asset,
        id: "master-asset-2",
        derived_from_id: "source-asset-2",
        storage_key: "production/wf-prod-123/prod-job-2/master.png",
        url: "http://localhost:9000/etsy/master2.png",
      },
      mockup_assets: [
        {
          id: "mockup-tshirt-new",
          workflow_id: "wf-prod-123",
          derived_from_id: "master-asset-2",
          storage_key: "production/wf-prod-123/prod-job-2/mockups/custom_tshirt_new.jpg",
          mime_type: "image/jpeg",
          byte_size: 150000,
          checksum_sha256: "sha256mockupTshirtNew",
          width: 1200,
          height: 1200,
          has_alpha: false,
          url: "http://localhost:9000/etsy/tshirt_new.jpg",
          provenance: {
            asset_type: "mockup",
            source: "user_template",
            template_id: "tpl-tshirt-new",
            product_type: "tshirt",
            template_name: "Black Bella Canvas Flatlay",
            source_asset_id: "master-asset-2",
            is_cover: true,
            listing_order: 1,
          },
        },
        {
          id: "mockup-mug-new",
          workflow_id: "wf-prod-123",
          derived_from_id: "master-asset-2",
          storage_key: "production/wf-prod-123/prod-job-2/mockups/custom_mug_new.jpg",
          mime_type: "image/jpeg",
          byte_size: 150000,
          checksum_sha256: "sha256mockupMugNew",
          width: 1200,
          height: 1200,
          has_alpha: false,
          url: "http://localhost:9000/etsy/mug_new.jpg",
          provenance: {
            asset_type: "mockup",
            source: "user_template",
            template_id: "tpl-mug-new",
            product_type: "mug",
            template_name: "Kitchen Scene Mug",
            source_asset_id: "master-asset-2",
            is_cover: false,
            listing_order: 2,
          },
        },
      ],
      mockup_urls: {
        tshirt: "http://localhost:9000/etsy/tshirt_new.jpg",
        mug: "http://localhost:9000/etsy/mug_new.jpg",
      },
    };

    currentProdJob = updatedProdJob;

    // Trigger data reload in the existing mounted component without page refresh
    await (wrapper.vm as any).loadData();
    await flushPromises();

    // Verify all mockups immediately render the new image URLs
    const updatedImgs = wrapper.findAll("img");
    const newTshirtImg = updatedImgs.find((img) => img.attributes("src")?.includes("tshirt_new.jpg"));
    const oldTshirtImg = updatedImgs.find((img) => img.attributes("src")?.includes("tshirt1.jpg"));

    expect(newTshirtImg).toBeDefined();
    expect(oldTshirtImg).toBeUndefined();
  });

  it("renders intended physical product tabs with zero count without adding dummy mockups", async () => {
    const jobWithTshirtOnly = {
      ...mockProductionSucceededJob,
      mockup_assets: [mockProductionSucceededJob.mockup_assets[0]], // only 1 T-shirt mockup
    };

    const workflowWithManyIntended = {
      ...mockApprovedWorkflow,
      intended_product_uses: ["tshirt", "mug", "tote_bag", "tumbler", "poster", "sweatshirt"],
    };

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(jobWithTshirtOnly);
      if (url.includes("/api/v1/workflows/wf-prod-123")) return Promise.resolve(workflowWithManyIntended);
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

    // T-Shirt tab with count 1 exists
    expect(wrapper.text()).toContain("T-Shirt");
    expect(wrapper.text()).toContain("1 listing mockup");

    // Intended physical products appear as empty tabs ready for template upload
    expect(wrapper.text()).toContain("Ceramic Mug");
    expect(wrapper.text()).toContain("Tote Bag");
    expect(wrapper.text()).toContain("Sweatshirt");
    expect(wrapper.text()).toContain("New Category");
  });

  it("renders intended product tabs with empty state when zero mockups exist across all products", async () => {
    const jobWithZeroMockups = {
      ...mockProductionSucceededJob,
      mockup_assets: [],
      mockup_urls: {},
    };

    const workflowWithoutIntended = {
      ...mockApprovedWorkflow,
      intended_product_uses: [],
    };

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(jobWithZeroMockups);
      if (url.includes("/api/v1/workflows/wf-prod-123")) return Promise.resolve(workflowWithoutIntended);
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

    // Assert generic empty state when zero tabs and zero mockups
    expect(wrapper.text()).toContain("No mockups selected yet");
    expect(wrapper.text()).toContain("Add your own product photos and position your master artwork");
    expect(wrapper.text()).toContain("Add Mockup");
  });

  it("adds new product tab immediately upon creating mockup and removes tab when deleting last mockup", async () => {
    let currentAssets: any[] = [
      {
        id: "mockup-tshirt-1",
        workflow_id: "wf-prod-123",
        storage_key: "production/wf-prod-123/mockups/custom_tshirt_1.jpg",
        mime_type: "image/jpeg",
        byte_size: 150000,
        checksum_sha256: "sha256mockup1",
        width: 1200,
        height: 1200,
        has_alpha: false,
        url: "http://localhost:9000/etsy/tshirt1.jpg",
        provenance: {
          asset_type: "mockup",
          source: "user_template",
          template_id: "tpl-tshirt-1",
          product_type: "tshirt",
          template_name: "Black Bella Canvas Flatlay",
          is_cover: true,
          listing_order: 1,
        },
      },
    ];

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/mockups/") && opts?.method === "DELETE") {
        const id = url.split("/").pop();
        currentAssets = currentAssets.filter((a) => a.id !== id);
        return Promise.resolve({ status: 204 });
      }
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) {
        return Promise.resolve({
          ...mockProductionSucceededJob,
          mockup_assets: currentAssets,
        });
      }
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

    // Initial state: only T-Shirt 1
    expect(wrapper.text()).toContain("T-Shirt");
    expect(wrapper.text()).not.toContain("Tote Bag");

    // Add a Tote Bag mockup
    const prodTabComp = wrapper.findComponent({ name: "WorkflowProductionTab" });
    expect(prodTabComp.exists()).toBe(true);

    const newToteAsset = {
      id: "mockup-tote-1",
      workflow_id: "wf-prod-123",
      storage_key: "production/wf-prod-123/mockups/custom_tote_bag_1.jpg",
      mime_type: "image/jpeg",
      byte_size: 150000,
      checksum_sha256: "sha256mockupTote",
      width: 1200,
      height: 1200,
      has_alpha: false,
      url: "http://localhost:9000/etsy/tote1.jpg",
      provenance: {
        asset_type: "mockup",
        source: "user_template",
        template_id: "tpl-tote-1",
        product_type: "tote_bag",
        template_name: "Canvas Tote Flatlay",
        is_cover: false,
        listing_order: 2,
      },
    };
    currentAssets.push(newToteAsset);

    prodTabComp.vm.handleCustomMockupCreated({
      mockup_url: "http://localhost:9000/etsy/tote1.jpg",
      asset_id: "mockup-tote-1",
      product_type: "tote_bag",
      template_id: "tpl-tote-1",
      template_name: "Canvas Tote Flatlay",
    });
    await flushPromises();

    // Now Tote Bag 1 tab appears
    expect(wrapper.text()).toContain("Tote Bag");

    // Delete the only Tote Bag mockup
    await prodTabComp.vm.handleDeleteMockup({
      id: "mockup-tote-1",
      workflow_id: "wf-prod-123",
      storage_key: "tote.jpg",
      mime_type: "image/jpeg",
      byte_size: 1000,
      checksum_sha256: "",
      width: 1200,
      height: 1200,
      has_alpha: false,
      url: "http://localhost:9000/etsy/tote1.jpg",
      provenance: { product_type: "tote_bag" },
    });
    await prodTabComp.vm.confirmDeleteMockup();
    await flushPromises();

    // Tote Bag tab completely disappears (no Tote Bag 0)
    expect(wrapper.text()).not.toContain("Tote Bag");
    expect(wrapper.text()).toContain("T-Shirt");
  });

  it("filters out any legacy/dummy mockups from gallery and displays only genuine user-uploaded templates", async () => {
    const jobWithDummyAndReal = {
      ...mockProductionSucceededJob,
      mockup_assets: [
        // Dummy Tote Bag Mockup (no user template)
        {
          id: "dummy-tote-1",
          workflow_id: "wf-prod-123",
          storage_key: "production/wf-prod-123/mockups/tote_dummy.jpg",
          mime_type: "image/jpeg",
          byte_size: 100000,
          checksum_sha256: "sha256dummy",
          width: 1200,
          height: 1200,
          has_alpha: false,
          url: "http://localhost:9000/etsy/tote_dummy.jpg",
          provenance: {
            pipeline: "mockup",
            asset_type: "mockup",
            product_type: "tote_bag",
            source: "fake",
            template_id: null,
          },
        },
        // Real User-Uploaded Tote Bag Mockup
        {
          id: "real-tote-1",
          workflow_id: "wf-prod-123",
          storage_key: "production/wf-prod-123/mockups/custom_tote_bag_real.jpg",
          mime_type: "image/jpeg",
          byte_size: 150000,
          checksum_sha256: "sha256real",
          width: 1200,
          height: 1200,
          has_alpha: false,
          url: "http://localhost:9000/etsy/tote_real.jpg",
          provenance: {
            phase: 7,
            asset_type: "mockup",
            source: "user_template",
            template_id: "tpl-real-tote-1",
            product_type: "tote_bag",
            template_name: "Fabric Tote Bag Mockup PSD",
            is_cover: true,
            listing_order: 1,
          },
        },
      ],
    };

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/workflows/wf-prod-123/research")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/concepts")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/artwork-jobs")) return Promise.resolve([]);
      if (url.includes("/api/v1/workflows/wf-prod-123/production")) return Promise.resolve(jobWithDummyAndReal);
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

    // Tote Bag count must be exactly 1 (NOT 2)
    expect(wrapper.text()).toContain("Tote Bag");
    expect(wrapper.text()).toContain("1 listing mockup");
    expect(wrapper.text()).not.toContain("2 listing mockups");

    // Real mockup name is rendered, dummy is NOT rendered
    expect(wrapper.text()).toContain("Fabric Tote Bag Mockup PSD");
    expect(wrapper.text()).not.toContain("Tote Bag Mockup 1");
  });
});
