import { describe, it, expect, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import ListingEditorCard from "../components/workflow/listing/ListingEditorCard.vue";

const IconMock = {
  template: '<i :data-icon="name" />',
  props: ["name"],
};

describe("ListingEditorCard Component with 3 Separate Fields & Targeted Regeneration", () => {
  const defaultProps = {
    title: "Kawaii Medical Equipment PNG, Radiology Tech Sublimation Design, MRI CT Scanner Clipart",
    description: "DIGITAL DOWNLOAD – PNG FILE ONLY\n\nHigh-res PNG.\n\nWHAT YOU WILL RECEIVE\n• Master PNG",
    shoppingCartSummary: "Cute kawaii medical equipment PNG with MRI characters. 4500x5400 px transparent file for shirts and scrubs.",
    aiDisclosure: "This artwork was created with the assistance of AI tools.",
    version: 1,
    isSaving: false,
    isGeneratingSeo: false,
    generatingTarget: null,
    hasUnsavedChanges: false,
  };

  it("renders Title, Shopping Cart Summary, and Description as 3 distinct editable fields", async () => {
    const wrapper = mount(ListingEditorCard, {
      props: defaultProps,
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // 1. Title Input
    const titleInput = wrapper.find("#listing-title");
    expect(titleInput.exists()).toBe(true);
    expect((titleInput.element as HTMLInputElement).value).toBe(defaultProps.title);

    // 2. Shopping Cart Summary Textarea
    const summaryInput = wrapper.find("#listing-summary");
    expect(summaryInput.exists()).toBe(true);
    expect((summaryInput.element as HTMLTextAreaElement).value).toBe(defaultProps.shoppingCartSummary);

    // 3. Description Textarea
    const descInput = wrapper.find("#listing-desc");
    expect(descInput.exists()).toBe(true);
    expect((descInput.element as HTMLTextAreaElement).value).toBe(defaultProps.description);
  });

  it("displays character counters for Title (140 max) and Shopping Cart Summary (200 max)", async () => {
    const wrapper = mount(ListingEditorCard, {
      props: defaultProps,
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // Title counter
    expect(wrapper.text()).toContain(`${defaultProps.title.length} / 140`);

    // Summary counter
    expect(wrapper.text()).toContain(`${defaultProps.shoppingCartSummary.length} / 200`);

    // Manual Etsy Field badge
    expect(wrapper.text()).toContain("Manual Etsy Field");
  });

  it("emits targeted SEO regeneration events for individual fields and Regenerate All", async () => {
    const wrapper = mount(ListingEditorCard, {
      props: defaultProps,
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // Regenerate Title button
    const titleRegenBtn = wrapper.findAll("button").find(b => b.text().includes("Regenerate Title"));
    expect(titleRegenBtn).toBeDefined();
    await titleRegenBtn!.trigger("click");
    expect(wrapper.emitted("generateSeo")).toBeTruthy();
    expect(wrapper.emitted("generateSeo")![0]).toEqual(["title"]);

    // Regenerate Summary button
    const summaryRegenBtn = wrapper.findAll("button").find(b => b.text().includes("Regenerate Summary"));
    expect(summaryRegenBtn).toBeDefined();
    await summaryRegenBtn!.trigger("click");
    expect(wrapper.emitted("generateSeo")![1]).toEqual(["shopping_cart_summary"]);

    // Regenerate Description button
    const descRegenBtn = wrapper.findAll("button").find(b => b.text().includes("Regenerate Description"));
    expect(descRegenBtn).toBeDefined();
    await descRegenBtn!.trigger("click");
    expect(wrapper.emitted("generateSeo")![2]).toEqual(["description"]);

    // Regenerate All button in header
    const allRegenBtn = wrapper.findAll("button").find(b => b.text().includes("Regenerate All"));
    expect(allRegenBtn).toBeDefined();
    await allRegenBtn!.trigger("click");
    expect(wrapper.emitted("generateSeo")![3]).toEqual(["all"]);
  });

  it("emits field update events when user edits Title, Description, or Shopping Cart Summary", async () => {
    const wrapper = mount(ListingEditorCard, {
      props: defaultProps,
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    // Edit Title
    const titleInput = wrapper.find("#listing-title");
    await titleInput.setValue("Updated Title PNG");
    expect(wrapper.emitted("update:title")).toBeTruthy();
    expect(wrapper.emitted("update:title")![0]).toEqual(["Updated Title PNG"]);

    // Edit Summary
    const summaryInput = wrapper.find("#listing-summary");
    await summaryInput.setValue("Updated Cart Summary PNG.");
    expect(wrapper.emitted("update:shoppingCartSummary")).toBeTruthy();
    expect(wrapper.emitted("update:shoppingCartSummary")![0]).toEqual(["Updated Cart Summary PNG."]);

    // Edit Description
    const descInput = wrapper.find("#listing-desc");
    await descInput.setValue("Updated Description text.");
    expect(wrapper.emitted("update:description")).toBeTruthy();
    expect(wrapper.emitted("update:description")![0]).toEqual(["Updated Description text."]);
  });

  it("copies shopping cart summary to clipboard when Copy button is clicked", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      configurable: true,
    });

    const wrapper = mount(ListingEditorCard, {
      props: defaultProps,
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    await flushPromises();

    const copyBtn = wrapper.findAll("button").find(b => b.text().includes("Copy"));
    expect(copyBtn).toBeDefined();
    await copyBtn!.trigger("click");
    await flushPromises();

    expect(writeTextMock).toHaveBeenCalledWith(defaultProps.shoppingCartSummary);
  });
});
