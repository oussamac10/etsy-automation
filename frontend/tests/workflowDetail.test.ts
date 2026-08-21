import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import workflowPage from "../pages/workflow/[id].vue";

// Mock vue-router module
vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: {
      id: "wf-123",
    },
  }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock Nuxt globals
vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

// Mock NavBar component
const NavBarMock = {
  template: "<div>NavBar Mock</div>",
};

const NuxtLinkMock = {
  template: "<a><slot /></a>",
};

const mockWorkflow = {
  id: "wf-123",
  owner_id: "user-123",
  idea_mode: "market-led",
  name: "US Trend Discovery - Aug 2026",
  target_marketplace: "etsy",
  target_country: "US",
  output_language: "en",
  target_buyer: "coffee lovers",
  intended_product_uses: ["mug"],
  state: "IDEA_REVIEW",
  version: 1,
  created_at: "2026-08-14T23:00:00Z",
  updated_at: "2026-08-14T23:00:00Z",
};

const mockOriginalIdea = {
  id: "idea-123",
  original_text: "A sleepy fox",
  slogan: "Keep Cozy",
  desired_style: "watercolor",
  audience: "fox lovers",
  occasion: "birthday",
  season: "winter",
  product_uses: ["mug"],
};

const mockConcept = {
  id: "concept-123",
  workflow_id: "wf-123",
  title: "Sleepy Fox Mug",
  description: "A cozy watercolor sleepy fox",
  origin: "market-led",
  differentiation: "Unique color scheme",
  risk_level: "low",
  score: 4.8,
  score_breakdown: { design: 5, appeal: 4.5 },
  status: "proposed",
  prompts: [
    {
      id: "prompt-123",
      concept_id: "concept-123",
      version: 1,
      positive_prompt: "sleepy fox",
      negative_prompt: "blurry",
      exact_slogan: "Keep Cozy",
    },
  ],
};

const mockArtworkJob = {
  id: "job-123",
  workflow_id: "wf-123",
  concept_id: "concept-123",
  provider: "recraft",
  provider_model: "recraftv4_1",
  status: "completed",
  assets: [
    {
      id: "asset-123",
      workflow_id: "wf-123",
      width: 1024,
      height: 1024,
      byte_size: 102400,
      mime_type: "image/png",
      url: "http://localhost:9000/assets/fox.png",
      derived_from_id: null,
    },
  ],
};

const fetchMock = vi.fn().mockImplementation((url: string) => {
  if (url.includes("/api/v1/workflows/wf-123/ideas")) {
    return Promise.resolve(mockOriginalIdea);
  }
  if (url.includes("/api/v1/workflows/wf-123/research")) {
    return Promise.resolve([]);
  }
  if (url.includes("/api/v1/workflows/wf-123/concepts")) {
    return Promise.resolve([mockConcept]);
  }
  if (url.includes("/api/v1/workflows/wf-123/artwork-jobs")) {
    return Promise.resolve([mockArtworkJob]);
  }
  if (url.includes("/api/v1/workflows/wf-123")) {
    return Promise.resolve(mockWorkflow);
  }
  return Promise.resolve({});
});

describe("Workflow Detail Page - Gate 1 and Phase 6 controls", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockWorkflow.state = "IDEA_REVIEW";
    mockConcept.status = "proposed";
    mockArtworkJob.assets = [];
  });

  it("renders Approve This Concept and Reject Concept in IDEA_REVIEW", async () => {
    vi.stubGlobal("$fetch", fetchMock);
    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(wrapper.text()).toContain("Approve This Concept");
    expect(wrapper.text()).toContain("Reject Concept");
    expect(wrapper.text()).toContain("Edit Prompt");
    expect(wrapper.text()).toContain("Choose one concept to continue.");
  });

  it("clicking Approve This Concept calls Gate 1 correctly", async () => {
    const postFetch = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", postFetch.mockImplementation((url: string) => {
      if (url.endsWith("/approvals")) {
        return Promise.resolve({ id: "approval-123" });
      }
      return fetchMock(url);
    }));

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    const approveBtn = wrapper.findAll("button").find(b => b.text() === "Approve This Concept");
    expect(approveBtn).toBeDefined();
    await approveBtn?.trigger("click");

    expect(postFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/workflows/wf-123/approvals"),
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          gate: "IDEA_APPROVAL",
          decision: "APPROVED",
          target_type: "ProductConcept",
          target_id: "concept-123",
          target_version: 1,
        }),
      })
    );
  });

  it("reveals artwork generation controls when Gate 1 is approved", async () => {
    mockWorkflow.state = "IDEA_APPROVED";
    mockConcept.status = "approved";
    mockArtworkJob.assets = [];

    vi.stubGlobal("$fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/artwork-jobs")) {
        return Promise.resolve([]);
      }
      return fetchMock(url);
    }));
    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(wrapper.text()).toContain("Artwork Generation & Approval");
    expect(wrapper.text()).not.toContain("Phase 6");
    expect(wrapper.text()).toContain("Your concept is approved. Generate artwork to continue.");
    expect(wrapper.text()).toContain("Generate Artwork");
  });

  it("clicking Generate Artwork calls the artwork creation endpoint", async () => {
    mockWorkflow.state = "IDEA_APPROVED";
    mockConcept.status = "approved";
    
    const postFetch = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", postFetch.mockImplementation((url: string) => {
      if (url.endsWith("/artwork")) {
        return Promise.resolve({ id: "job-123" });
      }
      if (url.includes("/artwork-jobs")) {
        return Promise.resolve([]);
      }
      return fetchMock(url);
    }));

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    const generateBtn = wrapper.findAll("button").find(b => b.text() === "Generate Artwork");
    expect(generateBtn).toBeDefined();
    await generateBtn?.trigger("click");

    expect(postFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/workflows/wf-123/artwork"),
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          provider: "recraft",
          provider_model: "recraftv4_1",
        }),
      })
    );
  });

  it("renders candidates and image preview URLs in ART_REVIEW", async () => {
    mockWorkflow.state = "ART_REVIEW";
    mockConcept.status = "approved";
    mockArtworkJob.assets = [
      {
        id: "asset-123",
        workflow_id: "wf-123",
        width: 1024,
        height: 1024,
        byte_size: 102400,
        mime_type: "image/png",
        url: "http://localhost:9000/assets/fox.png",
        derived_from_id: null,
      },
    ];

    vi.stubGlobal("$fetch", fetchMock);
    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    const img = wrapper.find("img");
    expect(img.exists()).toBe(true);
    expect(img.attributes("src")).toBe("http://localhost:9000/assets/fox.png");
    expect(wrapper.text()).toContain("Approve Artwork");
    expect(wrapper.text()).toContain("Refine Option");
  });

  it("approving artwork calls Gate 2 approval correctly", async () => {
    mockWorkflow.state = "ART_REVIEW";
    mockConcept.status = "approved";
    mockArtworkJob.assets = [
      {
        id: "asset-123",
        workflow_id: "wf-123",
        width: 1024,
        height: 1024,
        byte_size: 102400,
        mime_type: "image/png",
        url: "http://localhost:9000/assets/fox.png",
        derived_from_id: null,
      },
    ];

    const postFetch = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", postFetch.mockImplementation((url: string) => {
      if (url.endsWith("/approvals")) {
        return Promise.resolve({ id: "approval-456" });
      }
      return fetchMock(url);
    }));

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    const approveBtn = wrapper.findAll("button").find(b => b.text() === "Approve Artwork");
    expect(approveBtn).toBeDefined();
    await approveBtn?.trigger("click");

    expect(postFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/workflows/wf-123/approvals"),
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          gate: "ARTWORK_APPROVAL",
          decision: "APPROVED",
          target_type: "Asset",
          target_id: "asset-123",
        }),
      })
    );
  });

  it("opens candidate design full-size inspection modal and toggles background", async () => {
    mockWorkflow.state = "ART_REVIEW";
    mockConcept.status = "APPROVED";
    mockArtworkJob.assets = [
      {
        id: "asset-123",
        workflow_id: "wf-123",
        width: 1024,
        height: 1024,
        byte_size: 102400,
        mime_type: "image/png",
        url: "http://localhost:9000/assets/fox.png",
        derived_from_id: null,
      },
    ];

    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(workflowPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    // Initially modal is closed
    expect(wrapper.text()).not.toContain("Candidate Design #1 of 1");

    // Click inspect button
    const inspectBtn = wrapper.findAll("button").find(b => b.text().includes("Inspect"));
    expect(inspectBtn).toBeDefined();
    await inspectBtn?.trigger("click");

    // Modal should now be open
    expect(wrapper.text()).toContain("Candidate Design #1 of 1");
    expect(wrapper.text()).toContain("Transparent Alpha");
    expect(wrapper.text()).toContain("Checkerboard");
    expect(wrapper.text()).toContain("White");
    expect(wrapper.text()).toContain("Dark");
    expect(wrapper.text()).toContain("Download PNG");

    // Switch background to dark
    const darkBtn = wrapper.findAll("button").find(b => b.text().includes("Dark"));
    expect(darkBtn).toBeDefined();
    await darkBtn?.trigger("click");

    // Close preview modal by clicking the X button
    const closeBtn = wrapper.findAll("button").find(b => b.attributes("class")?.includes("hover:bg-secondary") && !b.text());
    expect(closeBtn).toBeDefined();
    await closeBtn?.trigger("click");

    expect(wrapper.text()).not.toContain("Candidate Design #1 of 1");
  });
});
