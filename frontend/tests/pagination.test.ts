import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import Pagination from "../components/ui/Pagination.vue";

const IconMock = {
  props: ["name"],
  template: "<i :data-icon='name' />",
};

describe("Pagination Component", () => {
  it("renders item range and page buttons correctly for 45 items with default pageSize (20 per page)", () => {
    const wrapper = mount(Pagination, {
      props: {
        currentPage: 1,
        totalItems: 45,
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    expect(wrapper.text()).toContain("Showing 1 to 20 of 45 results");
    // Should render page numbers 1, 2, 3
    const buttons = wrapper.findAll("button");
    const pageNums = buttons.map((b) => b.text()).filter((t) => t === "1" || t === "2" || t === "3");
    expect(pageNums).toEqual(["1", "2", "3"]);
  });

  it("calculates start and end items correctly for subsequent pages", () => {
    const wrapper = mount(Pagination, {
      props: {
        currentPage: 3,
        totalItems: 45,
        pageSize: 20,
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    expect(wrapper.text()).toContain("Showing 41 to 45 of 45 results");
  });

  it("emits update:currentPage and page-change on clicking next page button", async () => {
    const wrapper = mount(Pagination, {
      props: {
        currentPage: 1,
        totalItems: 45,
        pageSize: 20,
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    const nextBtn = wrapper.find('[data-testid="pagination-next-btn"]');
    expect(nextBtn.exists()).toBe(true);
    await nextBtn.trigger("click");

    expect(wrapper.emitted("update:currentPage")).toEqual([[2]]);
    expect(wrapper.emitted("page-change")).toEqual([[2]]);
  });

  it("disables prev button on page 1 and next button on last page", () => {
    const wrapperPage1 = mount(Pagination, {
      props: {
        currentPage: 1,
        totalItems: 45,
        pageSize: 20,
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    const prevBtn = wrapperPage1.find('[data-testid="pagination-prev-btn"]');
    expect(prevBtn.attributes("disabled")).toBeDefined();

    const wrapperPage3 = mount(Pagination, {
      props: {
        currentPage: 3,
        totalItems: 45,
        pageSize: 20,
      },
      global: {
        components: {
          Icon: IconMock,
        },
      },
    });

    const nextBtn = wrapperPage3.find('[data-testid="pagination-next-btn"]');
    expect(nextBtn.attributes("disabled")).toBeDefined();
  });
});
