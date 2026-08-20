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

  it('renders fit badge and reasons when fitness is loaded', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('fitness')) {
        return Promise.resolve({
          taxonomy_id: 6844,
          taxonomy_path: 'Craft Supplies & Tools > Canvas & Surfaces > Clip Art',
          fit_score: 0.95,
          fit_reasons: ['Sublimation compatible', 'Digital download'],
          warnings: [],
          has_mismatched_required_attributes: false,
        });
      }
      return Promise.resolve([]);
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(CategorySelectorCard, {
      props: {
        workflowId: 'wf-123',
        taxonomyId: 6844,
      },
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
        },
      },
    });

    await flushPromises();
    expect(wrapper.text()).toContain('95% fit');
    expect(wrapper.text()).toContain('Compatibility:');
    expect(wrapper.text()).toContain('Sublimation compatible');
  });

  it('opens category selection dialog and emits updateCategory event on confirm', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('fitness')) {
        return Promise.resolve({
          taxonomy_id: 6844,
          taxonomy_path: 'Craft Supplies & Tools > Canvas & Surfaces > Clip Art',
          fit_score: 0.85,
          fit_reasons: [],
          warnings: [],
          has_mismatched_required_attributes: false,
        });
      }
      return Promise.resolve([
        {
          id: 77,
          name: 'Digital',
          full_path: 'Art & Collectibles > Drawing & Illustration > Digital',
          level: 2,
          fit_score: 0.9,
          fit_reasons: ['Optimized for digital illustration'],
        },
      ]);
    });
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
    expect(wrapper.text()).toContain('90% fit');

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

  it('renders Poor fit badge and mismatch warning when category attributes mismatch campaign intent', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('fitness')) {
        return Promise.resolve({
          taxonomy_id: 6844,
          taxonomy_path: 'Craft Supplies & Tools > Canvas & Surfaces > Clip Art & Image Files',
          fit_score: 0.3,
          fit_level: 'poor',
          fit_reasons: ['Required Craft type values are limited to paper/collage uses.'],
          warnings: ['Required Craft type values are limited to paper/collage uses and do not match apparel/sublimation intent.'],
          has_mismatched_required_attributes: true,
          blocking_mismatch: true,
          mismatched_required_reason: 'Craft type is required, but Etsy only offers paper/collage-related values.',
        });
      }
      return Promise.resolve([]);
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(CategorySelectorCard, {
      props: {
        workflowId: 'wf-123',
        taxonomyId: 6844,
      },
      global: {
        stubs: {
          Icon: true,
          Teleport: true,
        },
      },
    });

    await flushPromises();
    expect(wrapper.text()).toContain('Poor fit');
    expect(wrapper.text()).toContain("Required attributes do not match this campaign's intended use.");
  });
});

