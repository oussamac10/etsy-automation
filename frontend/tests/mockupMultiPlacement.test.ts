import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import MockupPlacementControls from "../components/workflow/mockup-modal/MockupPlacementControls.vue";
import MockupPlacementCanvas from "../components/workflow/mockup-modal/MockupPlacementCanvas.vue";
import type { MockupPlacement } from "../types/mockup";

describe("Mockup Multi-Placement Print Zones Suite", () => {
  const samplePlacements: MockupPlacement[] = [
    {
      id: "zone-1",
      left_pct: 15,
      top_pct: 20,
      width_pct: 35,
      height_pct: 35,
      angle_deg: -10,
      blend_mode: "multiply",
      artwork_source_id: null,
    },
    {
      id: "zone-2",
      left_pct: 55,
      top_pct: 20,
      width_pct: 35,
      height_pct: 35,
      angle_deg: 10,
      blend_mode: "multiply",
      artwork_source_id: "variant-2",
    },
    {
      id: "zone-3",
      left_pct: 35,
      top_pct: 60,
      width_pct: 30,
      height_pct: 30,
      angle_deg: 0,
      blend_mode: "overlay",
      artwork_source_id: null,
    },
  ];

  describe("MockupPlacementControls Component (Multi-Zone)", () => {
    it("renders active zone placement controls and alignment actions", async () => {
      const wrapper = mount(MockupPlacementControls, {
        props: {
          placements: samplePlacements,
          activePlacementIndex: 1,
          variants: [
            { id: "variant-1", name: "Red Variant", url: "http://localhost/red.png" },
            { id: "variant-2", name: "Blue Variant", url: "http://localhost/blue.png" },
          ],
          templateName: "Sticker Sheet 3-Pack",
          saveToLibrary: false,
          isCover: false,
          isCompositing: false,
          isUploadingNew: false,
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      // 1. Check active zone placement header and coordinates
      expect(wrapper.text()).toContain("Zone 2 Placement");
      expect(wrapper.text()).toContain("55%"); // leftPct for zone 2
      expect(wrapper.text()).toContain("20%"); // topPct for zone 2

      // 2. Click Center All button
      const centerAllBtn = wrapper.findAll("button").find((b) => b.text().includes("Center All"));
      expect(centerAllBtn?.exists()).toBe(true);
      await centerAllBtn?.trigger("click");
      expect(wrapper.emitted("centerBoth")).toBeTruthy();

      // 3. Click Center X button
      const centerXBtn = wrapper.findAll("button").find((b) => b.text().includes("Center X"));
      expect(centerXBtn?.exists()).toBe(true);
      await centerXBtn?.trigger("click");
      expect(wrapper.emitted("centerHorizontal")).toBeTruthy();
    });
  });

  describe("MockupPlacementCanvas Component (Multi-Zone Rendering)", () => {
    it("renders all print zones with active zone interactive handle and inactive zones selectable", async () => {
      const wrapper = mount(MockupPlacementCanvas, {
        props: {
          templateImageUrl: "http://localhost:8000/test-template.png",
          masterImageUrl: "http://localhost:8000/test-master.png",
          placements: samplePlacements,
          activePlacementIndex: 0,
          variants: [
            { id: "variant-1", name: "Red Variant", url: "http://localhost/red.png" },
            { id: "variant-2", name: "Blue Variant", url: "http://localhost/blue.png" },
          ],
          viewMode: "edit",
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      // 1. All 3 artwork preview images are rendered in Layer 1
      const artworkImgs = wrapper.findAll('img[alt^="Artwork Zone"]');
      expect(artworkImgs.length).toBe(3);

      // 2. Active zone has primary dashed bounding box and stalk handle
      const activeBox = wrapper.find(".cursor-move");
      expect(activeBox.exists()).toBe(true);
      const activeStyle = activeBox.attributes("style") || "";
      expect(activeStyle).toContain("rotate(-10deg)");

      // 3. Inactive zones are rendered with selectable outlines
      const inactiveBoxes = wrapper.findAll(".group\\/zone");
      expect(inactiveBoxes.length).toBe(2);

      // 4. Clicking an inactive zone selects it
      await inactiveBoxes[0].trigger("mousedown");
      expect(wrapper.emitted("update:activePlacementIndex")).toBeTruthy();
    });
  });
});
