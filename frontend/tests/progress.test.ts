import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import Progress from "../components/ui/Progress.vue";

describe("Progress Component", () => {
  it("renders with modelValue and computes translateX transform correctly", () => {
    const wrapper = mount(Progress, {
      props: {
        modelValue: 18,
        max: 100,
      },
    });

    const root = wrapper.find('[role="progressbar"]');
    expect(root.attributes("aria-valuenow")).toBe("18");
    const indicator = wrapper.find(".bg-primary");
    expect(indicator.attributes("style")).toContain("transform: translateX(-82%);");
  });

  it("renders with value prop and computes translateX transform correctly", () => {
    const wrapper = mount(Progress, {
      props: {
        value: 50,
        max: 100,
      },
    });

    const root = wrapper.find('[role="progressbar"]');
    expect(root.attributes("aria-valuenow")).toBe("50");
    const indicator = wrapper.find(".bg-primary");
    expect(indicator.attributes("style")).toContain("transform: translateX(-50%);");
  });

  it("clamps values between 0 and 100%", () => {
    const wrapperOver = mount(Progress, {
      props: {
        modelValue: 150,
        max: 100,
      },
    });

    const indicator = wrapperOver.find(".bg-primary");
    expect(indicator.attributes("style")).toContain("transform: translateX(-0%);");
  });
});
