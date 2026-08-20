import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { useArtworkVariants } from "../composables/useArtworkVariants";
import ArtworkVariantsCard from "../components/workflow/production/ArtworkVariantsCard.vue";

vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

const IconMock = {
  props: ["name"],
  template: '<span :data-icon="name" class="icon-mock" />',
};

const mockVariants = [
  {
    id: "var-1",
    workflow_id: "wf-123",
    derived_from_id: "master-1",
    storage_key: "workflows/wf-123/variants/var-1/dark_shirt.png",
    mime_type: "image/png",
    byte_size: 2048,
    checksum_sha256: "abc123sha",
    width: 4500,
    height: 5400,
    has_alpha: true,
    variant_type: "dark_shirt",
    variant_status: "ready",
    title: "Dark Shirt Version",
    custom_color: "#F5E6C8",
    custom_instructions: null,
    prompt_version: "color-variant-v2-deterministic",
    url: "https://storage.test/dark_shirt.png",
    validation_report: {
      is_valid: true,
      format: "image/png",
      has_real_alpha: true,
      checkerboard_free: true,
      source_composition_preserved: true,
    },
    created_at: "2026-08-20T12:00:00Z",
  },
  {
    id: "var-2",
    workflow_id: "wf-123",
    derived_from_id: "master-1",
    storage_key: "workflows/wf-123/variants/var-2/light_shirt.png",
    mime_type: "image/png",
    byte_size: 2048,
    checksum_sha256: "def456sha",
    width: 4500,
    height: 5400,
    has_alpha: true,
    variant_type: "light_shirt",
    variant_status: "approved",
    title: "Light Shirt Version",
    custom_color: "#1A1A1A",
    custom_instructions: null,
    prompt_version: "color-variant-v2-deterministic",
    url: "https://storage.test/light_shirt.png",
    validation_report: {
      is_valid: true,
      format: "image/png",
      has_real_alpha: true,
      checkerboard_free: true,
      source_composition_preserved: true,
    },
    created_at: "2026-08-20T12:05:00Z",
  },
];

describe("useArtworkVariants composable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and sets variants successfully", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockVariants);
    vi.stubGlobal("$fetch", fetchMock);

    const { variants, approvedVariants, fetchVariants } = useArtworkVariants();
    await fetchVariants("wf-123");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/workflows/wf-123/artwork-variants",
      expect.anything()
    );
    expect(variants.value).toHaveLength(2);
    expect(approvedVariants.value).toHaveLength(1);
    expect(approvedVariants.value[0].id).toBe("var-2");
  });

  it("approves variant and updates status", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockVariants)
      .mockResolvedValueOnce({
        ...mockVariants[0],
        variant_status: "approved",
      });
    vi.stubGlobal("$fetch", fetchMock);

    const { variants, fetchVariants, approveVariant, approvedVariants } = useArtworkVariants();
    await fetchVariants("wf-123");

    const success = await approveVariant("wf-123", "var-1");
    expect(success).toBe(true);
    expect(variants.value.find((v) => v.id === "var-1")?.variant_status).toBe("approved");
    expect(approvedVariants.value).toHaveLength(2);
  });

  it("toggles package inclusion and updates variant state", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockVariants)
      .mockResolvedValueOnce({
        ...mockVariants[1],
        include_in_buyer_package: true,
      });
    vi.stubGlobal("$fetch", fetchMock);

    const { variants, fetchVariants, togglePackageInclusion } = useArtworkVariants();
    await fetchVariants("wf-123");

    const success = await togglePackageInclusion("wf-123", "var-2", true);
    expect(success).toBe(true);
    expect(variants.value.find((v) => v.id === "var-2")?.include_in_buyer_package).toBe(true);
  });
});

describe("ArtworkVariantsCard component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockVariants));
  });

  it("renders variant cards with selective package inclusion controls", async () => {
    const wrapper = mount(ArtworkVariantsCard, {
      props: {
        workflowId: "wf-123",
        masterImageUrl: "https://storage.test/master.png",
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // Check title and approved badge
    expect(wrapper.text()).toContain("Garment Color Variants");

    // Check variant titles
    expect(wrapper.text()).toContain("Dark Shirt Version");
    expect(wrapper.text()).toContain("Light Shirt Version");

    // Check Include in Buyer Package controls
    expect(wrapper.text()).toContain("Include in Buyer Package");

    // Check 6-point validation checklist
    expect(wrapper.text()).toContain("Validation Checklist");
    expect(wrapper.text()).toContain("Format: PNG (300 DPI)");
    expect(wrapper.text()).toContain("Real Alpha (No JPEG)");
    expect(wrapper.text()).toContain("Zero Checkerboard");
    expect(wrapper.text()).toContain("Pass");

    // Check status tags
    expect(wrapper.text()).toContain("Ready for Review");
    expect(wrapper.text()).toContain("Approved");

    // Check background toggle buttons
    const bgButtons = wrapper.findAll("button[title*='Background'], button[title*='Checkerboard']");
    expect(bgButtons.length).toBeGreaterThanOrEqual(4);
  });
});

describe("CustomerPackagePreviewCard component", () => {
  const mockPreviewResponse = {
    workflow_id: "wf-123",
    files: [
      {
        type: "original",
        name: "Original Master PNG",
        filename: "NovaCraft_Fox_Original.png",
        byte_size: 14500000,
        included: true,
        status: "ready",
        asset_id: "master-1",
      },
      {
        type: "dark_shirt",
        name: "Dark Shirt Version",
        filename: "NovaCraft_Fox_Dark_Shirt.png",
        byte_size: 14600000,
        included: true,
        status: "ready",
        asset_id: "var-1",
      },
      {
        type: "readme",
        name: "Usage & Print Guide",
        filename: "NovaCraft_Fox_README.txt",
        byte_size: 2500,
        included: true,
        status: "ready",
        asset_id: null,
      },
      {
        type: "license",
        name: "Commercial License",
        filename: "NovaCraft_Fox_LICENSE.txt",
        byte_size: 1800,
        included: true,
        status: "ready",
        asset_id: null,
      },
    ],
    included_count: 2,
    estimated_total_bytes: 29104300,
    needs_rebuild: true,
    etsy_files_out_of_sync: true,
    package_asset: {
      id: "asset-pkg-1",
      byte_size: 26000000,
    },
    package_download_url: "https://storage.test/package.zip",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("$fetch", vi.fn().mockResolvedValue(mockPreviewResponse));
  });

  it("renders itemized buyer deliverables table and sync warning banner", async () => {
    const CustomerPackagePreviewCard = (await import("../components/workflow/production/CustomerPackagePreviewCard.vue")).default;
    const wrapper = mount(CustomerPackagePreviewCard, {
      props: {
        workflowId: "wf-123",
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Buyer Deliverable ZIP Package");
    expect(wrapper.text()).toContain("Etsy Digital Files Out of Sync");
    expect(wrapper.text()).toContain("Sync Updated Files");
    expect(wrapper.text()).toContain("Rebuild Required");
    expect(wrapper.text()).toContain("Original Master PNG");
    expect(wrapper.text()).toContain("Dark Shirt Version");
    expect(wrapper.text()).toContain("Usage & Print Guide");
    expect(wrapper.text()).toContain("Commercial License");
    expect(wrapper.text()).toContain("NovaCraft_Fox_Dark_Shirt.png");
    expect(wrapper.text()).toContain("Etsy File Limit");
  });
});
