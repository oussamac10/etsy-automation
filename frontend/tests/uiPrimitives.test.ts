import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import Pagination from '../components/ui/Pagination.vue';
import Progress from '../components/ui/Progress.vue';
import ServiceStatus from '../components/ServiceStatus.vue';

const IconMock = {
  props: ['name'],
  template: "<i :data-icon='name' />",
};

describe('Pagination Component', () => {
  it('renders item range and page buttons correctly for 45 items with default pageSize (20 per page)', () => {
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

    expect(wrapper.text()).toContain('Showing 1 to 20 of 45 results');
    const buttons = wrapper.findAll('button');
    const pageNums = buttons.map((b) => b.text()).filter((t) => t === '1' || t === '2' || t === '3');
    expect(pageNums).toEqual(['1', '2', '3']);
  });

  it('calculates start and end items correctly for subsequent pages', () => {
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

    expect(wrapper.text()).toContain('Showing 41 to 45 of 45 results');
  });

  it('emits update:currentPage and page-change on clicking next page button', async () => {
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
    await nextBtn.trigger('click');

    expect(wrapper.emitted('update:currentPage')).toEqual([[2]]);
    expect(wrapper.emitted('page-change')).toEqual([[2]]);
  });

  it('disables prev button on page 1 and next button on last page', () => {
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
    expect(prevBtn.attributes('disabled')).toBeDefined();

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
    expect(nextBtn.attributes('disabled')).toBeDefined();
  });
});

describe('Progress Component', () => {
  it('renders with modelValue and computes translateX transform correctly', () => {
    const wrapper = mount(Progress, {
      props: {
        modelValue: 18,
        max: 100,
      },
    });

    const root = wrapper.find('[role="progressbar"]');
    expect(root.attributes('aria-valuenow')).toBe('18');
    const indicator = wrapper.find('.bg-primary');
    expect(indicator.attributes('style')).toContain('transform: translateX(-82%);');
  });

  it('renders with value prop and computes translateX transform correctly', () => {
    const wrapper = mount(Progress, {
      props: {
        value: 50,
        max: 100,
      },
    });

    const root = wrapper.find('[role="progressbar"]');
    expect(root.attributes('aria-valuenow')).toBe('50');
    const indicator = wrapper.find('.bg-primary');
    expect(indicator.attributes('style')).toContain('transform: translateX(-50%);');
  });

  it('clamps values between 0 and 100%', () => {
    const wrapperOver = mount(Progress, {
      props: {
        modelValue: 150,
        max: 100,
      },
    });

    const indicator = wrapperOver.find('.bg-primary');
    expect(indicator.attributes('style')).toContain('transform: translateX(-0%);');
  });
});

describe('ServiceStatus Component', () => {
  it('renders a text label, not colour alone', () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: 'redis', status: 'ok' },
    });
    expect(wrapper.text()).toContain('redis');
    expect(wrapper.text()).toContain('Healthy');
  });

  it('labels a down component', () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: 'database', status: 'down', detail: 'ConnectionError' },
    });
    expect(wrapper.text()).toContain('Unavailable');
    expect(wrapper.text()).toContain('ConnectionError');
  });

  it('shows latency when provided', () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: 'redis', status: 'ok', latencyMs: 7 },
    });
    expect(wrapper.text()).toContain('7 ms');
  });

  it('falls back to unknown for an unrecognised status', () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: 'redis', status: 'unknown' },
    });
    expect(wrapper.text()).toContain('Unknown');
  });

  it('hides the decorative symbol from assistive technology', () => {
    const wrapper = mount(ServiceStatus, {
      props: { name: 'redis', status: 'ok' },
    });
    expect(wrapper.find('[aria-hidden="true"]').exists()).toBe(true);
  });
});
