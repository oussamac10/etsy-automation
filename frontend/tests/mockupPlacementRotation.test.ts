import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import MockupPlacementControls from "../components/workflow/mockup-modal/MockupPlacementControls.vue";
import MockupPlacementCanvas from "../components/workflow/mockup-modal/MockupPlacementCanvas.vue";
import { BLEND_MODE_OPTIONS, getBlendModeInfo } from "../utils/mockupProducts";

describe("Mockup Placement & Rotation Suite", () => {
  describe("Blend Mode Formatters & Options", () => {
    it("returns correct blend mode information", () => {
      const overInfo = getBlendModeInfo("over");
      expect(overInfo.value).toBe("over");
      expect(overInfo.shortLabel).toBe("Solid / Opaque");

      const multiplyInfo = getBlendModeInfo("multiply");
      expect(multiplyInfo.value).toBe("multiply");
      expect(multiplyInfo.shortLabel).toBe("Multiply");

      const overlayInfo = getBlendModeInfo("overlay");
      expect(overlayInfo.value).toBe("overlay");
      expect(overlayInfo.shortLabel).toBe("Overlay");
    });

    it("has all 6 supported blend modes configured with icons and badges", () => {
      expect(BLEND_MODE_OPTIONS.length).toBe(6);
      const values = BLEND_MODE_OPTIONS.map((b) => b.value);
      expect(values).toContain("over");
      expect(values).toContain("multiply");
      expect(values).toContain("overlay");
      expect(values).toContain("soft-light");
      expect(values).toContain("screen");
      expect(values).toContain("darken");
    });
  });

  describe("MockupPlacementControls Component", () => {
    it("renders rotation angle slider, quick angle buttons, and emits updates", async () => {
      const wrapper = mount(MockupPlacementControls, {
        props: {
          leftPct: 25,
          topPct: 25,
          widthPct: 50,
          heightPct: 50,
          angleDeg: 15,
          blendMode: "multiply",
          templateName: "Test Mockup",
          saveToLibrary: false,
          isCover: true,
          isCompositing: false,
          isUploadingNew: false,
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      expect(wrapper.text()).toContain("Rotation Angle");
      expect(wrapper.text()).toContain("15°");

      const angleSlider = wrapper.find('input[type="range"][max="180"]');
      expect(angleSlider.exists()).toBe(true);

      await angleSlider.setValue(-30);
      expect(wrapper.emitted("update:angleDeg")?.[0]).toEqual([-30]);

      const buttons = wrapper.findAll("button");
      const quick90Btn = buttons.find((b) => b.text().includes("+90°"));
      expect(quick90Btn?.exists()).toBe(true);
      await quick90Btn?.trigger("click");
      expect(wrapper.emitted("update:angleDeg")).toBeTruthy();
    });
  });

  describe("MockupPlacementCanvas Component Rotation Transform", () => {
    it("applies CSS transform rotate for non-zero angleDeg and renders rotation handle in edit mode", () => {
      const wrapper = mount(MockupPlacementCanvas, {
        props: {
          templateImageUrl: "http://localhost:8000/test-template.png",
          masterImageUrl: "http://localhost:8000/test-master.png",
          leftPct: 28,
          topPct: 25,
          widthPct: 44,
          heightPct: 48,
          angleDeg: 45,
          blendMode: "multiply",
          viewMode: "edit",
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      const editBox = wrapper.find(".cursor-move");
      expect(editBox.exists()).toBe(true);

      const style = editBox.attributes("style") || "";
      expect(style).toContain("rotate(45deg)");
      expect(style).toContain("left: 28%");
      expect(style).toContain("top: 25%");
      expect(style).toContain("width: 44%");
      expect(style).toContain("height: 48%");

      const rotateHandle = wrapper.find('[title="Drag to rotate artwork"]');
      expect(rotateHandle.exists()).toBe(true);
    });
  });
});
