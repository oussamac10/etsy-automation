import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import EtsyDraftCard from '../components/workflow/listing/EtsyDraftCard.vue';
import type { ListingDraft } from '../types/listing';

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBase: 'http://localhost:8000',
  },
}));

vi.stubGlobal('useRoute', () => ({
  query: {},
}));

vi.stubGlobal('useRouter', () => ({
  replace: vi.fn(),
}));

const mockBaseListing: ListingDraft = {
  id: 'draft-101',
  workflow_id: 'wf-101',
  title: 'Vintage Botanical Wildflower PNG Sublimation Design',
  description: 'High resolution digital download file for printing.',
  tags: ['botanical png', 'wildflower clipart', 'sublimation design'],
  price_minor_units: 499,
  currency: 'USD',
  taxonomy_id: 77,
  ip_risk_level: 'low',
  ip_findings: {},
  version: 1,
};

describe('Etsy Listing Dispatch Progress & State UI Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders initial not_started state with Ready for Dispatch badge and Create Etsy Draft button', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'READY_FOR_ETSY_DRAFT',
        listing: {
          ...mockBaseListing,
          etsy_dispatch_status: 'not_started',
        },
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="etsy-badge-ready"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etsy-create-draft-btn"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etsy-dispatching-progress"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="etsy-completed-panel"]').exists()).toBe(false);
  });

  it('renders in-progress stepper when dispatch is creating listing', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      if (url.includes('/etsy/status')) {
        return Promise.resolve({
          workflow_id: 'wf-101',
          dispatch_status: 'creating_listing',
          current_step: 'create_listing',
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'READY_FOR_ETSY_DRAFT',
        listing: {
          ...mockBaseListing,
          etsy_dispatch_status: 'creating_listing',
        },
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="etsy-badge-progress"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Creating Draft');
    expect(wrapper.text()).toContain('Dispatching Draft to Etsy Open API v3...');
    expect(wrapper.text()).toContain('In Progress');
    expect(wrapper.find('[data-testid="etsy-dispatching-progress"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etsy-completed-panel"]').exists()).toBe(false);
  });

  it('renders step 3 active with completed previous steps when uploading files', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'READY_FOR_ETSY_DRAFT',
        listing: {
          ...mockBaseListing,
          etsy_listing_id: '4559404921',
          etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
          etsy_dispatch_status: 'uploading_file',
        },
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="etsy-badge-progress"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Creating Draft');
    expect(wrapper.text()).toContain('In Progress');
    expect(wrapper.text()).toContain('1. Create Listing');
    expect(wrapper.text()).toContain('2. Upload Mockups');
    expect(wrapper.text()).toContain('3. Upload Digital Files');
    expect(wrapper.text()).toContain('4. Apply Attributes');
    // Does NOT render the completed stats panel while uploading
    expect(wrapper.find('[data-testid="etsy-completed-panel"]').exists()).toBe(false);
  });

  it('REGRESSION TEST: Completed draft displays Draft Created + Complete without In Progress or spinner', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      if (url.includes('/etsy/status')) {
        return Promise.resolve({
          workflow_id: 'wf-101',
          dispatch_status: 'completed',
          current_step: null,
          etsy_listing_id: '4559404921',
          etsy_state: 'draft',
          etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
          etsy_file_ids: ['file-1', 'file-2'],
          steps: {
            create_listing: { status: 'completed' },
            upload_mockups: { status: 'completed', uploaded_count: 4 },
            upload_files: { status: 'completed', uploaded_count: 2 },
            apply_attributes: { status: 'completed' },
          },
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const completedListing: ListingDraft = {
      ...mockBaseListing,
      etsy_listing_id: '4559404921',
      etsy_shop_id: 'shop-123',
      etsy_state: 'draft',
      etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
      etsy_file_id: 'file-1',
      etsy_file_ids: ['file-1', 'file-2'],
      etsy_dispatch_status: 'completed',
    };

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'ETSY_DRAFT_CREATED',
        listing: completedListing,
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    // Top badge must strictly be Draft Created
    expect(wrapper.find('[data-testid="etsy-badge-completed"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etsy-badge-progress"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Draft Created');

    // Stepper must show completion text and Complete badge
    expect(wrapper.text()).toContain('Etsy draft created successfully.');
    expect(wrapper.text()).toContain('Complete');
    expect(wrapper.text()).not.toContain('In Progress');
    expect(wrapper.text()).not.toContain('Dispatching Draft to Etsy Open API v3...');

    // Stats Grid must display accurate counts
    expect(wrapper.find('[data-testid="etsy-completed-panel"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('4559404921');
    expect(wrapper.text()).toContain('Draft (Safe)');
    expect(wrapper.text()).toContain('4 Mockups');
    expect(wrapper.text()).toContain('2 Real Files Attached');

    // Action buttons must be present
    expect(wrapper.find('[data-testid="etsy-open-manager-btn"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('All Drafts');
  });

  it('self-heals stale in-progress status on load when draft is fully created in Etsy', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      if (url.includes('/etsy/status')) {
        return Promise.resolve({
          workflow_id: 'wf-101',
          dispatch_status: 'completed',
          etsy_listing_id: '4559404921',
          etsy_state: 'draft',
          etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
          etsy_file_ids: ['file-1', 'file-2'],
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    // Stale listing from interrupted session where dispatch_status remained uploading_file
    const staleListing: ListingDraft = {
      ...mockBaseListing,
      etsy_listing_id: '4559404921',
      etsy_shop_id: 'shop-123',
      etsy_state: 'draft',
      etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
      etsy_file_ids: ['file-1', 'file-2'],
      etsy_dispatch_status: 'uploading_file',
    };

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'ETSY_DRAFT_CREATED',
        listing: staleListing,
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    // After polling returns completed, UI renders completed state cleanly
    expect(wrapper.find('[data-testid="etsy-badge-completed"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Complete');
    expect(wrapper.text()).not.toContain('In Progress');
  });

  it('renders failure alert and Retry button on dispatch failure', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-123',
          shop_name: 'NovaCraftPixel',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const failedListing: ListingDraft = {
      ...mockBaseListing,
      etsy_dispatch_status: 'failed',
      etsy_failure_reason: 'Etsy API Rate Limit Exceeded (429)',
    };

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'READY_FOR_ETSY_DRAFT',
        listing: failedListing,
      },
      global: {
        stubs: { Icon: true, NuxtLink: true },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="etsy-badge-failed"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Draft Failed');
    expect(wrapper.text()).toContain('Etsy API Rate Limit Exceeded (429)');
    expect(wrapper.text()).toContain('Retry Dispatch');
  });
});
