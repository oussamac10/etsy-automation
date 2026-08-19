import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import TagEditorCard from "../components/workflow/listing/TagEditorCard.vue";

describe("TagEditorCard Component", () => {
  const initialTags = [
    "png download",
    "sublimation shirt",
    "vintage mushroom",
    "cottagecore art",
    "retro vibes",
    "digital print",
    "clipart file",
    "dtg ready",
    "shirt sublimation",
    "mug graphic",
    "transparent png",
    "commercial use",
    "instant download",
  ];

  it("renders 13 active tags and collapsed campaign history by default", async () => {
    const wrapper = mount(TagEditorCard, {
      props: {
        tags: initialTags,
        tagHistory: ["old tag 1", "vintage mushroom"],
        isSaving: false,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    expect(wrapper.text()).toContain("13 / 13 tags");
    expect(wrapper.text()).toContain("Active Campaign Tags");
    expect(wrapper.text()).toContain("Campaign Tag History & Removed Tags");

    // History is closed by default
    expect(wrapper.text()).not.toContain("All History");

    // Expand history
    const historyHeaderBtn = wrapper.findAll('button[type="button"]').find(b => b.text().includes("Campaign Tag History"));
    await historyHeaderBtn?.trigger("click");

    // "old tag 1" is in history
    expect(wrapper.text()).toContain("old tag 1");
  });

  it("removes a tag, emits update:tags, and moves it to removed history", async () => {
    const wrapper = mount(TagEditorCard, {
      props: {
        tags: initialTags,
        tagHistory: [],
        isSaving: false,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    const removeBtn = wrapper.find('button[title="Remove tag (moves to campaign history)"]');
    expect(removeBtn.exists()).toBe(true);
    await removeBtn.trigger("click");

    expect(wrapper.emitted("update:tags")).toBeTruthy();
    const emittedTags = wrapper.emitted("update:tags")![0][0] as string[];
    expect(emittedTags.length).toBe(12);
    expect(emittedTags).not.toContain("png download");

    // Expand history to verify removed tag
    const historyHeaderBtn = wrapper.findAll('button[type="button"]').find(b => b.text().includes("Campaign Tag History"));
    await historyHeaderBtn?.trigger("click");

    // The removed tag should now have a "Restore" button in history
    expect(wrapper.text()).toContain("Restore");
  });

  it("restores a removed tag when clicking restore", async () => {
    const twelveTags = initialTags.slice(0, 12);
    const wrapper = mount(TagEditorCard, {
      props: {
        tags: twelveTags,
        tagHistory: ["instant download"],
        isSaving: false,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    expect(wrapper.text()).toContain("12 / 13 tags");

    // Expand history
    const historyHeaderBtn = wrapper.findAll('button[type="button"]').find(b => b.text().includes("Campaign Tag History"));
    await historyHeaderBtn?.trigger("click");

    const restoreBtn = wrapper.find('button[title="Restore \'instant download\' to active tags"]');
    expect(restoreBtn.exists()).toBe(true);
    await restoreBtn.trigger("click");

    expect(wrapper.emitted("update:tags")).toBeTruthy();
    const emittedTags = wrapper.emitted("update:tags")![0][0] as string[];
    expect(emittedTags.length).toBe(13);
    expect(emittedTags).toContain("instant download");
  });

  it("shows notice when attempting to restore beyond 13 tags", async () => {
    const wrapper = mount(TagEditorCard, {
      props: {
        tags: initialTags,
        tagHistory: ["extra bonus tag"],
        isSaving: false,
      },
      global: {
        stubs: {
          Icon: { template: "<i />" },
        },
      },
    });

    // Expand history
    const historyHeaderBtn = wrapper.findAll('button[type="button"]').find(b => b.text().includes("Campaign Tag History"));
    await historyHeaderBtn?.trigger("click");

    const restoreBtn = wrapper.find('button[title="13 tags maximum reached. Remove a tag first."]');
    expect(restoreBtn.exists()).toBe(true);
    await restoreBtn.trigger("click");

    expect(wrapper.text()).toContain("Cannot restore");
    expect(wrapper.emitted("update:tags")).toBeFalsy();
  });
});
