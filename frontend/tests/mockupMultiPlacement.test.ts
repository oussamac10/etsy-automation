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
    it("renders Print Zones bar with tabs and allows zone selection, addition, duplication, and deletion", async () => {
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

      // 1. Check multi-zone header and zone tabs
      expect(wrapper.text()).toContain("Print Zones (3)");
      expect(wrapper.text()).toContain("Zone 1");
      expect(wrapper.text()).toContain("Zone 2");
      expect(wrapper.text()).toContain("Zone 3");

      // 2. Click Add Zone button
      const addZoneBtn = wrapper.findAll("button").find((b) => b.text().includes("Add Zone"));
      expect(addZoneBtn?.exists()).toBe(true);
      await addZoneBtn?.trigger("click");
      expect(wrapper.emitted("addZone")).toBeTruthy();

      // 3. Click Duplicate button
      const dupBtn = wrapper.findAll("button").find((b) => b.text().includes("Duplicate"));
      expect(dupBtn?.exists()).toBe(true);
      await dupBtn?.trigger("click");
      expect(wrapper.emitted("duplicateZone")?.[0]).toEqual([1]); // duplicated active index 1

      // 4. Click Zone 1 tab
      const zone1Tab = wrapper.findAll("button").find((b) => b.text().includes("Zone 1"));
      expect(zone1Tab?.exists()).toBe(true);
      await zone1Tab?.trigger("click");
      expect(wrapper.emitted("update:activePlacementIndex")?.[0]).toEqual([0]);

      // 5. Artwork variant dropdown for zone
      const select = wrapper.find("select");
      expect(select.exists()).toBe(true);
      await select.setValue("variant-1");
      expect(wrapper.emitted("updateZoneArtworkSource")?.[0]).toEqual([
        { index: 1, sourceId: "variant-1" },
      ]);
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
