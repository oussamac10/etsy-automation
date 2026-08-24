import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IndexPage from "../pages/index.vue";
import LandingNavbar from "../components/landing/LandingNavbar.vue";
import HeroWorkflowDemo from "../components/landing/HeroWorkflowDemo.vue";
import MockupShowcase from "../components/landing/MockupShowcase.vue";
import IpScreeningSection from "../components/landing/IpScreeningSection.vue";
import EtsyDraftSection from "../components/landing/EtsyDraftSection.vue";
import { useAuthStore } from "../stores/auth";

// Global stubs for Nuxt components
const NuxtLinkStub = {
  name: "NuxtLink",
  props: ["to"],
  template: '<a :href="to" :data-to="to"><slot /></a>',
};

const IconStub = {
  name: "Icon",
  props: ["name"],
  template: '<span class="icon-stub" :data-icon="name"></span>',
};

// Global mocks for Nuxt composables
vi.stubGlobal("useHead", vi.fn());
vi.stubGlobal("useRuntimeConfig", () => ({
  public: { apiBase: "http://localhost:8000" },
}));
vi.stubGlobal("useRequestHeaders", () => ({}));

// Stub window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Stub IntersectionObserver
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

describe("Public Landing Page (NovaCraftPixel)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();

    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  function mountLandingPage() {
    return mount(IndexPage, {
      global: {
        stubs: {
          NuxtLink: NuxtLinkStub,
          Icon: IconStub,
          ClientOnly: { template: "<div><slot /></div>" },
        },
      },
    });
  }

  it("renders public landing page with all core landmarks", () => {
    const wrapper = mountLandingPage();

    // Verify main landmarks
    expect(wrapper.find("header").exists()).toBe(true);
    expect(wrapper.find("main#main").exists()).toBe(true);
    expect(wrapper.find("footer").exists()).toBe(true);

    // Verify primary hero headline is present
    expect(wrapper.text()).toContain("Turn Etsy opportunities into ready-to-list digital products.");
    expect(wrapper.text()).toContain("NovaCraftPixel");
  });

  describe("Authentication-Aware CTAs", () => {
    it("renders unauthenticated CTAs pointing to /register and /login when signed out", () => {
      const auth = useAuthStore();
      auth.user = null;
      auth.initialized = true;

      const wrapper = mountLandingPage();

      // Navbar links
      const registerNavBtn = wrapper.find('[data-testid="landing-nav-register-link"]');
      expect(registerNavBtn.exists()).toBe(true);
      expect(registerNavBtn.attributes("data-to")).toBe("/register");

      const loginNavBtn = wrapper.find('[data-testid="landing-nav-login-link"]');
      expect(loginNavBtn.exists()).toBe(true);
      expect(loginNavBtn.attributes("data-to")).toBe("/login");

      // Hero primary CTA
      const heroCta = wrapper.find('[data-testid="hero-primary-cta"]');
      expect(heroCta.exists()).toBe(true);
      expect(heroCta.attributes("data-to")).toBe("/register");
      expect(heroCta.text()).toContain("Start Creating");

      // Final CTA
      const finalCta = wrapper.find('[data-testid="final-cta-primary"]');
      expect(finalCta.exists()).toBe(true);
      expect(finalCta.attributes("data-to")).toBe("/register");
    });

    it("renders authenticated CTAs pointing to /dashboard when signed in", () => {
      const auth = useAuthStore();
      auth.user = { id: "user-123", email: "creator@example.com", is_active: true };
      auth.initialized = true;

      const wrapper = mountLandingPage();

      // Navbar dashboard link
      const dashboardNavBtn = wrapper.find('[data-testid="landing-nav-dashboard-link"]');
      expect(dashboardNavBtn.exists()).toBe(true);
      expect(dashboardNavBtn.attributes("data-to")).toBe("/dashboard");
      expect(dashboardNavBtn.text()).toContain("Open Dashboard");

      // Hero primary CTA
      const heroCta = wrapper.find('[data-testid="hero-primary-cta"]');
      expect(heroCta.exists()).toBe(true);
      expect(heroCta.attributes("data-to")).toBe("/dashboard");
      expect(heroCta.text()).toContain("Open Dashboard");

      // Final CTA
      const finalCta = wrapper.find('[data-testid="final-cta-primary"]');
      expect(finalCta.exists()).toBe(true);
      expect(finalCta.attributes("data-to")).toBe("/dashboard");
      expect(finalCta.text()).toContain("Open Dashboard");
    });
  });

  describe("Landing Navigation & Mobile Drawer", () => {
    it("toggles mobile menu drawer on button click", async () => {
      const wrapper = mount(LandingNavbar, {
        global: {
          stubs: {
            NuxtLink: NuxtLinkStub,
            Icon: IconStub,
            ThemeToggle: { template: "<button>theme</button>" },
          },
        },
      });

      expect(wrapper.find('[data-testid="mobile-menu-drawer"]').exists()).toBe(false);

      const toggleBtn = wrapper.find('[data-testid="mobile-menu-toggle"]');
      await toggleBtn.trigger("click");

      expect(wrapper.find('[data-testid="mobile-menu-drawer"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="mobile-menu-drawer"]').text()).toContain("How It Works");
    });
  });

  describe("Hero Workflow Mini-Demo", () => {
    it("allows interactive step switching across all 7 stages", async () => {
      const wrapper = mount(HeroWorkflowDemo, {
        global: {
          stubs: {
            NuxtLink: NuxtLinkStub,
            Icon: IconStub,
          },
        },
      });

      expect(wrapper.find('[data-testid="hero-workflow-demo"]').exists()).toBe(true);

      // Verify Step 1 is rendered initially
      expect(wrapper.find('[data-testid="demo-step-1"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("Demand Signals");

      // Click step 4 button (Artwork Master)
      const tabButtons = wrapper.findAll('button[role="tab"]');
      expect(tabButtons.length).toBe(7);

      await tabButtons[3].trigger("click");
      expect(wrapper.find('[data-testid="demo-step-4"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("Master 300 DPI Transparent PNG");

      // Click step 7 button (Etsy Draft Ready)
      await tabButtons[6].trigger("click");
      expect(wrapper.find('[data-testid="demo-step-7"]').exists()).toBe(true);
      expect(wrapper.text()).toContain("Etsy Draft Ready ✓");
    });
  });

  describe("Mockup Showcase", () => {
    it("renders all 9 standard catalog product options and handles selection", async () => {
      const wrapper = mount(MockupShowcase, {
        global: {
          stubs: {
            Icon: IconStub,
          },
        },
      });

      const buttons = wrapper.findAll("button");
      expect(buttons.length).toBe(9);

      // Verify key catalog products exist
      const text = wrapper.text();
      expect(text).toContain("Graphic T-Shirt");
      expect(text).toContain("Cozy Sweatshirt");
      expect(text).toContain("Ceramic Mug");
      expect(text).toContain("Skinny Tumbler");
      expect(text).toContain("Canvas Tote Bag");
      expect(text).toContain("Art Poster");
      expect(text).toContain("Die-Cut Sticker");
      expect(text).toContain("Phone Case");
      expect(text).toContain("Scented Candle");

      // Select Ceramic Mug
      const mugButton = buttons.find((b) => b.text().includes("Ceramic Mug"));
      expect(mugButton).toBeDefined();
      await mugButton!.trigger("click");

      expect(wrapper.text()).toContain("Sublimation Wrap");
    });
  });

  describe("Copy, Terminology & Legal Compliance", () => {
    it("contains zero development or internal phase terminology", () => {
      const wrapper = mountLandingPage();
      const pageText = wrapper.text();

      // Forbidden internal dev / phase terminology
      const forbiddenTerms = [
        "Phase 5",
        "Phase 6",
        "Phase 7",
        "Phase 8",
        "Phase 9",
        "Gate 1",
        "Gate 2",
        "Gate 3",
        "MVP",
        "fake mode",
        "worker",
        "pipeline adapter",
      ];

      for (const term of forbiddenTerms) {
        expect(pageText).not.toContain(term);
      }
    });

    it("displays mandatory preliminary screening disclaimer in IP section", () => {
      const wrapper = mount(IpScreeningSection, {
        global: {
          stubs: {
            Icon: IconStub,
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Preliminary automated trademark screening only — not legal advice.");
      expect(text).not.toContain("Trademark safe");
      expect(text).not.toContain("Legally approved");
      expect(text).not.toContain("Guaranteed non-infringing");
    });

    it("explicitly confirms Etsy integration is draft-only and publishes manually", () => {
      const wrapper = mount(EtsyDraftSection, {
        global: {
          stubs: {
            Icon: IconStub,
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Your listing is prepared as an Etsy draft. You review and publish it directly from your Etsy Shop Manager.");
      expect(text).toContain("Zero Unreviewed Autopublishing");
      expect(text).toContain("We never publish listings live automatically.");
    });
  });
});
