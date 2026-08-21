import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import {
  formatWorkflowStage,
  formatApprovalAction,
  formatProviderName,
  sanitizeUserErrorMessage,
} from "../utils/formatters";
import WorkflowStageNav from "../components/workflow/WorkflowStageNav.vue";
import WorkflowOverviewTab from "../components/workflow/WorkflowOverviewTab.vue";
import ProductionStatusCard from "../components/workflow/production/ProductionStatusCard.vue";
import WorkflowHeader from "../components/workflow/WorkflowHeader.vue";
import CategorySelectorCard from "../components/workflow/listing/CategorySelectorCard.vue";

describe("Product Polish & Clean UI Assertions", () => {
  describe("Formatters & Sanitization", () => {
    it("maps raw statuses to clean product names", () => {
      expect(formatWorkflowStage("READY_FOR_ETSY_DRAFT")).toBe("Ready for Etsy");
      expect(formatWorkflowStage("IDEA_REVIEW")).toBe("Review Concepts");
      expect(formatWorkflowStage("ART_REVIEW")).toBe("Review Artwork");
      expect(formatWorkflowStage("ARTWORK_APPROVED")).toBe("Artwork Approved");
      expect(formatWorkflowStage("PRODUCTION")).toBe("Production & Mockups");
      expect(formatWorkflowStage("ETSY_DRAFT_CREATED")).toBe("Draft Created");
      expect(formatWorkflowStage("PUBLISHED")).toBe("Published");
    });

    it("maps approval gates to action verbs", () => {
      expect(formatApprovalAction("IDEA_APPROVAL")).toBe("Approve Concept");
      expect(formatApprovalAction("ARTWORK_APPROVAL")).toBe("Approve Artwork");
      expect(formatApprovalAction("LISTING_APPROVAL")).toBe("Approve Listing");
    });

    it("maps providers to clean display names", () => {
      expect(formatProviderName("recraft")).toBe("Recraft");
      expect(formatProviderName("gemini")).toBe("Google Gemini");
      expect(formatProviderName("openai")).toBe("OpenAI");
      expect(formatProviderName("tavily")).toBe("Tavily");
    });

    it("sanitizes technical gate error messages for end users", () => {
      expect(sanitizeUserErrorMessage("requires gate IDEA_APPROVAL to be approved")).toBe(
        "Please approve the concept before proceeding."
      );
      expect(sanitizeUserErrorMessage("requires gate ARTWORK_APPROVAL to be approved")).toBe(
        "Please approve an artwork design before proceeding."
      );
      expect(sanitizeUserErrorMessage("requires gate LISTING_APPROVAL to be approved")).toBe(
        "Please complete the listing review before proceeding."
      );
      expect(sanitizeUserErrorMessage("GateNotSatisfiedError: cannot be decided while in RESEARCHING")).toBe(
        "This milestone is not ready for review yet."
      );
    });
  });

  describe("WorkflowStageNav Component", () => {
    it("renders clean step titles and no Gate badges", () => {
      const wrapper = mount(WorkflowStageNav, {
        props: {
          activeTab: "overview",
          workflowState: "READY_FOR_ETSY_DRAFT",
          conceptsCount: 3,
          candidatesCount: 2,
          productionStatus: "SUCCEEDED",
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Overview & Brief");
      expect(text).toContain("1. Concepts & Research");
      expect(text).toContain("2. Artwork Studio");
      expect(text).toContain("3. Production & Mockups");
      expect(text).toContain("4. Listing & IP Review");
      expect(text).toContain("5. Etsy Draft");

      // Assert no development gate badges or old dispatch terminology
      expect(text).not.toContain("Gate 3");
      expect(text).not.toContain("Gate 2");
      expect(text).not.toContain("Gate 1");
      expect(text).not.toContain("Etsy Dispatch");
      expect(text).toContain("Approved");
    });
  });

  describe("WorkflowOverviewTab Component", () => {
    it("renders Step 1, Step 2, Step 3 without Phase labels", () => {
      const wrapper = mount(WorkflowOverviewTab, {
        props: {
          workflow: {
            id: "wf-test-1",
            owner_id: "usr-1",
            name: "Test Campaign",
            state: "ART_REVIEW",
            idea_mode: "market-led",
            target_marketplace: "etsy",
            target_country: "US",
            output_language: "en",
            version: 1,
            created_at: "2026-08-15T00:00:00Z",
            updated_at: "2026-08-15T00:00:00Z",
          } as any,
          originalIdea: null,
          latestRun: null,
          latestProductionJob: null,
          pendingWorkflowId: null,
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
            Button: { template: "<button><slot /></button>" },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Step 1");
      expect(text).toContain("Step 2");
      expect(text).toContain("Step 3");
      expect(text).not.toContain("Phase 1-3");
      expect(text).not.toContain("Phase 4-6");
      expect(text).not.toContain("Phase 7-8");
    });
  });

  describe("ProductionStatusCard Component", () => {
    it("renders clean copy without Gate 1 / Gate 2 / Sharp references", () => {
      const wrapper = mount(ProductionStatusCard, {
        props: {
          state: "ARTWORK_APPROVED",
          latestProductionJob: null,
          isProductionLoading: false,
          exactSlogan: "COFFEE FIRST",
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Approved Slogan:");
      expect(text).toContain("COFFEE FIRST");
      expect(text).not.toContain("Recorded Gate 1 Slogan:");
      expect(text).not.toContain("Phase 7");
    });

    it("renders Artwork Selection Required when artwork not selected", () => {
      const wrapper = mount(ProductionStatusCard, {
        props: {
          state: "IDEA_REVIEW",
          latestProductionJob: null,
          isProductionLoading: false,
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
            NuxtLink: { template: "<a><slot /></a>" },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Artwork Selection Required");
      expect(text).not.toContain("Gate 2");
      expect(text).not.toContain("Phase 7");
    });
  });

  describe("WorkflowHeader Component", () => {
    it("renders title and badges without raw UUID prefix", () => {
      const wrapper = mount(WorkflowHeader, {
        props: {
          workflow: {
            id: "11111111-2222-3333-4444-555555555555",
            owner_id: "usr-1",
            name: "Summer Minimalist T-Shirts",
            idea_mode: "market-led",
            target_marketplace: "etsy",
            target_country: "US",
            output_language: "en",
            version: 1,
            state: "ART_REVIEW",
            created_at: "2026-08-15T00:00:00Z",
            updated_at: "2026-08-15T00:00:00Z",
          } as any,
          latestProductionJob: null,
          isWorkflowRunning: false,
          displayStageLabel: "Review Artwork",
          pendingWorkflowId: null,
          controlError: null,
        },
        global: {
          stubs: {
            Icon: { template: "<i />" },
            NuxtLink: { template: "<a><slot /></a>" },
            Badge: { template: "<span><slot /></span>" },
            Button: { template: "<button><slot /></button>" },
          },
        },
      });

      const text = wrapper.text();
      expect(text).toContain("Summer Minimalist T-Shirts");
      expect(text).not.toContain("ID: 11111111-2222-3333-4444-555555555555");
    });
  });
});
