import { createPinia, setActivePinia } from "pinia";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import usagePage from "../pages/usage.vue";
import { useAuthStore } from "~/stores/auth";

// Mock Nuxt globals
vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

vi.stubGlobal("useRequestHeaders", () => ({}));
const pushMock = vi.fn();
vi.stubGlobal("useRouter", () => ({
  push: pushMock,
}));

// Mock components
const NuxtLinkMock = {
  template: "<a><slot /></a>",
};

const NavBarMock = {
  template: "<div>NavBar Mock</div>",
};

const IconMock = {
  props: ["name"],
  template: "<i :data-icon='name' />",
};

const mockSummary = {
  currency: "USD",
  today_spent: "0.45",
  daily_budget: "2.00",
  daily_usage_pct: 22.5,
  month_spent: "12.80",
  monthly_budget: "30.00",
  monthly_usage_pct: 42.7,
  total_spent: "45.60",
  total_input_tokens: 150000,
  total_output_tokens: 35000,
  total_tokens: 185000,
  total_images: 24,
  total_calls: 58,
  is_paused: false,
  notify_on_budget_warning: true,
  by_provider: [
    { provider: "gemini", cost_decimal: "0.25", tokens: 120000, percentage: 55.6 },
    { provider: "recraft", cost_decimal: "0.20", tokens: 0, percentage: 44.4 },
  ],
  by_operation: [
    { operation: "text_synthesis", cost_decimal: "0.25", calls: 30, percentage: 55.6 },
    { operation: "image_generation", cost_decimal: "0.20", calls: 10, percentage: 44.4 },
  ],
  updated_at: new Date().toISOString(),
};

const mockLedger = {
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      workflow_id: "22222222-2222-2222-2222-222222222222",
      workflow_name: "Vintage Coffee Mug",
      created_at: new Date().toISOString(),
      provider: "gemini",
      service: "gemini-2.5-flash",
      operation: "text_synthesis",
      input_units: 1200,
      output_units: 450,
      unit_kind: "tokens",
      currency: "USD",
      estimated_cost: "0.0012",
      actual_cost: "0.0011",
      effective_cost: "0.0011",
      status: "reconciled",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

describe("Token Usage & Cost Controls Page", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    document.cookie = "etsy_csrf=test-csrf-token-12345";
    const auth = useAuthStore();
    auth.user = {
      id: "owner-123",
      email: "owner@test.com",
      role: "owner",
      display_name: "Shop Owner",
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    } as any;
    auth.initialized = true;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads and renders usage summary stats and token metrics", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/usage/summary")) return Promise.resolve(mockSummary);
      if (url.includes("/api/v1/usage/ledger")) return Promise.resolve(mockLedger);
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(usagePage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Token Usage & Cost Controls");
    expect(wrapper.find('[data-testid="today-spent"]').text()).toContain("$0.45");
    expect(wrapper.find('[data-testid="month-spent"]').text()).toContain("$12.80");
    expect(wrapper.find('[data-testid="total-tokens"]').text()).toContain("185,000");
    expect(wrapper.text()).toContain("Vintage Coffee Mug");
  });

  it("opens budget modal and saves updated budget limits", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url.includes("/api/v1/usage/budget") && opts?.method === "POST") {
        return Promise.resolve({
          ...mockSummary,
          daily_budget: "5.00",
          monthly_budget: "50.00",
        });
      }
      if (url.includes("/api/v1/usage/summary")) return Promise.resolve(mockSummary);
      if (url.includes("/api/v1/usage/ledger")) return Promise.resolve(mockLedger);
      return Promise.resolve({});
    });
    vi.stubGlobal("$fetch", fetchMock);

    const wrapper = mount(usagePage, {
      attachTo: document.body,
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // Click edit budgets button
    const editBtn = wrapper.find('[data-testid="edit-budgets-btn"]');
    expect(editBtn.exists()).toBe(true);
    await editBtn.trigger("click");

    expect(document.body.textContent).toContain("Configure Budget Ceilings");

    // Fill daily and monthly budget inputs
    const dailyInput = document.querySelector("#daily-budget") as HTMLInputElement;
    dailyInput.value = "5";
    dailyInput.dispatchEvent(new Event("input"));

    const monthlyInput = document.querySelector("#monthly-budget") as HTMLInputElement;
    monthlyInput.value = "50";
    monthlyInput.dispatchEvent(new Event("input"));

    // Save button inside dialog
    const saveBtn = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Save Changes")
    );
    expect(saveBtn).toBeDefined();
    saveBtn?.click();
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/usage/budget"),
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          daily_budget: 5,
          monthly_budget: 50,
        }),
      })
    );
    wrapper.unmount();
  });
});
