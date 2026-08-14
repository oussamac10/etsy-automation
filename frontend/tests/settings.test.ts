import { createPinia, setActivePinia } from "pinia";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import settingsPage from "../pages/settings.vue";

// Mock Nuxt globals
vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

vi.stubGlobal("useRequestHeaders", () => ({}));

// Mock Nuxt link component
const NuxtLinkMock = {
  template: "<a><slot /></a>",
};

// Mock NavBar component
const NavBarMock = {
  template: "<div>NavBar Mock</div>",
};

function stubFetch(telegramMock: any) {
  const fetchMock = vi.fn().mockImplementation((url: string, options?: any) => {
    if (url.includes("/settings/credentials")) {
      return Promise.resolve({ items: [] });
    }
    return telegramMock(url, options);
  });
  vi.stubGlobal("$fetch", fetchMock);
  return fetchMock;
}

describe("settings page - Telegram card", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    document.cookie = "etsy_csrf=test-csrf-token-12345";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("loads and displays unpaired state", async () => {
    const telegramMock = vi.fn().mockResolvedValue({
      paired: false,
      telegram_username: null,
      pairing_code_expires_at: null,
    });
    const fetchMock = stubFetch(telegramMock);

    const wrapper = mount(settingsPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    // Let mount tick
    await vi.dynamicImportSettled();
    await wrapper.vm.$nextTick();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/settings/telegram",
      expect.any(Object)
    );
    expect(wrapper.find('[data-testid="telegram-unpaired-container"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="telegram-paired-container"]').exists()).toBe(false);
  });

  it("loads and displays paired state", async () => {
    const telegramMock = vi.fn().mockResolvedValue({
      paired: true,
      telegram_username: "john_doe",
      pairing_code_expires_at: null,
    });
    const fetchMock = stubFetch(telegramMock);

    const wrapper = mount(settingsPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await vi.dynamicImportSettled();
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="telegram-paired-container"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="telegram-username"]').text()).toContain("@john_doe");
  });

  it("handles pairing code generation and handles CSRF validation", async () => {
    const telegramMock = vi.fn()
      .mockResolvedValueOnce({
        paired: false,
        telegram_username: null,
        pairing_code_expires_at: null,
      })
      .mockResolvedValueOnce({
        pairing_code: "123456",
        expires_at: new Date(Date.now() + 300000).toISOString(), // 5 mins
      });

    const fetchMock = stubFetch(telegramMock);

    const wrapper = mount(settingsPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await vi.dynamicImportSettled();
    await wrapper.vm.$nextTick();

    // Click generate code button
    const btn = wrapper.find('[data-testid="generate-pairing-code-btn"]');
    await btn.trigger("click");
    await wrapper.vm.$nextTick();

    // Verify it sent a POST request with the CSRF header
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/settings/telegram/pairing-code",
      expect.objectContaining({
        method: "POST",
        headers: { "x-csrf-token": "test-csrf-token-12345" },
      })
    );

    // Verify pairing code is split and rendered
    expect(wrapper.find('[data-testid="pairing-code"]').text()).toBe("123 456");
  });

  it("handles pairing code expiration countdown", async () => {
    const expiresAt = new Date(Date.now() + 120000); // 2 mins
    const telegramMock = vi.fn()
      .mockResolvedValueOnce({
        paired: false,
        telegram_username: null,
        pairing_code_expires_at: null,
      })
      .mockResolvedValueOnce({
        pairing_code: "123456",
        expires_at: expiresAt.toISOString(),
      });

    const fetchMock = stubFetch(telegramMock);

    const wrapper = mount(settingsPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await vi.dynamicImportSettled();
    await wrapper.vm.$nextTick();

    const btn = wrapper.find('[data-testid="generate-pairing-code-btn"]');
    await btn.trigger("click");
    await wrapper.vm.$nextTick();

    // Verify initial timer text
    expect(wrapper.find('[data-testid="pairing-code-countdown"]').text()).toContain("Expires in 2m 0s");

    // Advance time by 65 seconds
    vi.advanceTimersByTime(65000);
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="pairing-code-countdown"]').text()).toContain("Expires in 0m 55s");

    // Advance time by another 60 seconds (expiry)
    vi.advanceTimersByTime(60000);
    await wrapper.vm.$nextTick();

    // The pairing code element should be hidden since it's expired
    expect(wrapper.find('[data-testid="pairing-code"]').exists()).toBe(false);
  });

  it("handles bot disconnect with CSRF token check", async () => {
    const telegramMock = vi.fn()
      .mockResolvedValueOnce({
        paired: true,
        telegram_username: "john_doe",
        pairing_code_expires_at: null,
      })
      .mockResolvedValueOnce({}); // DELETE ok

    const fetchMock = stubFetch(telegramMock);

    const wrapper = mount(settingsPage, {
      global: {
        components: {
          NavBar: NavBarMock,
          NuxtLink: NuxtLinkMock,
        },
      },
    });

    await vi.dynamicImportSettled();
    await wrapper.vm.$nextTick();

    // Click disconnect button
    const btn = wrapper.find('[data-testid="disconnect-btn"]');
    await btn.trigger("click");
    await wrapper.vm.$nextTick();

    // Verify it sent a DELETE request with the CSRF header
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/settings/telegram",
      expect.objectContaining({
        method: "DELETE",
        headers: { "x-csrf-token": "test-csrf-token-12345" },
      })
    );

    // Verify unpaired state is restored
    expect(wrapper.find('[data-testid="telegram-unpaired-container"]').exists()).toBe(true);
  });
});
