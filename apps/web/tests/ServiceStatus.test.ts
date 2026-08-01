import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ServiceStatus from "../components/ServiceStatus.vue";

describe("ServiceStatus", () => {
  it("renders a text label, not colour alone", () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: "redis", status: "ok" },
    });
    expect(wrapper.text()).toContain("redis");
    expect(wrapper.text()).toContain("Healthy");
  });

  it("labels a down component", () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: "database", status: "down", detail: "ConnectionError" },
    });
    expect(wrapper.text()).toContain("Unavailable");
    expect(wrapper.text()).toContain("ConnectionError");
  });

  it("shows latency when provided", () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: "redis", status: "ok", latencyMs: 7 },
    });
    expect(wrapper.text()).toContain("7 ms");
  });

  it("falls back to unknown for an unrecognised status", () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: "redis", status: "unknown" },
    });
    expect(wrapper.text()).toContain("Unknown");
  });

  it("hides the decorative symbol from assistive technology", () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: "redis", status: "ok" },
    });
    expect(wrapper.find('[aria-hidden="true"]').exists()).toBe(true);
  });
});
