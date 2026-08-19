import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import CategorySelectorCard from '~/components/workflow/listing/CategorySelectorCard.vue';

describe('CategorySelectorCard Component', () => {
  it('renders default category when no taxonomy is provided', () => {
    const wrapper = mount(CategorySelectorCard, {
      props: {
        workflowId: 'wf-123',
      },
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Etsy Seller Category');
    expect(wrapper.text()).toContain('Clip Art & Image Files');
    expect(wrapper.text()).toContain('6844');
    expect(wrapper.text()).toContain('Change Category');
  });

  it('renders custom category path and ID when provided', () => {
    const wrapper = mount(CategorySelectorCard, {
      props: {
        workflowId: 'wf-123',
        taxonomyId: 2078,
        taxonomyPath: 'Art & Collectibles > Prints > Digital Prints',
      },
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Art & Collectibles > Prints > Digital Prints');
    expect(wrapper.text()).toContain('2078');
  });

  it('opens category selection dialog and emits updateCategory event on confirm', async () => {
    const fetchMock = vi.fn().mockResolvedValue([
      {
        id: 77,
        name: 'Digital',
        full_path: 'Art & Collectibles > Drawing & Illustration > Digital',
        level: 2,
      },
    ]);
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(CategorySelectorCard, {
      props: {
        workflowId: 'wf-123',
        taxonomyId: 6844,
        taxonomyPath: 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files',
      },
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
        },
      },
    });

    // Click Change Category button
    const changeBtn = wrapper.findAll('button').find((b) => b.text().includes('Change Category'));
    expect(changeBtn).toBeDefined();
    await changeBtn?.trigger('click');
    await flushPromises();

    // Verify dialog content is rendered
    expect(wrapper.text()).toContain('Select Etsy Digital Category');

    // Click apply category button
    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('Apply Category'));
    expect(applyBtn).toBeDefined();
    await applyBtn?.trigger('click');

    expect(wrapper.emitted('updateCategory')).toBeTruthy();
    expect(wrapper.emitted('updateCategory')?.[0]?.[0]).toEqual({
      id: 6844,
      path: 'Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files',
    });
  });
});
