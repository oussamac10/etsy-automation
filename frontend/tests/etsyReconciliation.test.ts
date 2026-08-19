import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import EtsyDraftCard from '../components/workflow/listing/EtsyDraftCard.vue';
import { useEtsy } from '../composables/useEtsy';
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

const mockListing: ListingDraft = {
  id: 'draft-123',
  workflow_id: 'wf-123',
  title: 'Vintage Celestial Moon PNG Sublimation Design',
  description: 'High quality 4500x5400 px digital PNG download.',
  tags: [
    'celestial png', 'moon sublimation', 'vintage moon', 'mystic graphic',
    'witchy vibes', 'astronomy clipart', 'digital download', 'shirt design',
    'printable art', 'tshirt transfer', 'cricut craft', 'boho astronomy',
    'aesthetic moon',
  ],
  price_minor_units: 499,
  currency: 'USD',
  ip_risk_level: 'low',
  ip_findings: {},
  version: 1,
  etsy_listing_id: 'listing-999',
  etsy_image_ids: ['img-1'],
  etsy_file_id: 'file-1',
  etsy_file_ids: ['file-1'],
  etsy_dispatch_status: 'completed',
};

describe('Etsy Reconciliation Frontend Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('reconcileEtsyDraft calls the reconcile endpoint in useEtsy', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      workflow_id: 'wf-123',
      dispatch_status: 'draft_removed',
      etsy_listing_id: null,
    });
    vi.stubGlobal('$fetch', fetchMock);

    const { reconcileEtsyDraft, draftStatus } = useEtsy();
    const result = await reconcileEtsyDraft('wf-123');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/workflows/wf-123/etsy/reconcile'),
      expect.objectContaining({ method: 'POST' })
    );
    expect(result?.dispatch_status).toBe('draft_removed');
    expect(draftStatus.value?.dispatch_status).toBe('draft_removed');
  });

  it('renders Etsy Draft Removed badge and alert when draft was deleted on Etsy', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/integrations/etsy')) {
        return Promise.resolve({
          connected: true,
          shop_id: 'shop-888',
          shop_name: 'StarlightCrafts',
          connection_status: 'connected',
          granted_scopes: ['listings_w'],
          token_health: 'valid',
        });
      }
      if (url.includes('/etsy/status')) {
        return Promise.resolve({
          workflow_id: 'wf-123',
          dispatch_status: 'draft_removed',
          etsy_listing_id: null,
        });
      }
      return Promise.resolve({});
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-123',
        workflowState: 'ETSY_DRAFT_CREATED',
        listing: mockListing,
      },
      global: {
        stubs: {
          Icon: true,
          NuxtLink: true,
        },
      },
    });

    await flushPromises();

    // Verify draft removed badge is displayed
    expect(wrapper.find('[data-testid="etsy-badge-removed"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Etsy Draft Removed');

    // Verify draft removed alert is rendered
    expect(wrapper.find('[data-testid="etsy-draft-removed-alert"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('This draft no longer exists in Etsy. Your campaign and digital files are still available locally.');

    // Verify Create Etsy Draft button is visible and active
    const createBtn = wrapper.find('[data-testid="etsy-create-draft-btn"]');
    expect(createBtn.exists()).toBe(true);
    expect(createBtn.text()).toContain('Create Etsy Draft');
  });

  it('stops polling cleanly when component is unmounted', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      connected: true,
      connection_status: 'connected',
    });
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-123',
        workflowState: 'READY_FOR_ETSY_DRAFT',
        listing: {
          ...mockListing,
          etsy_listing_id: null,
          etsy_dispatch_status: 'not_started',
        },
      },
      global: {
        stubs: {
          Icon: true,
          NuxtLink: true,
        },
      },
    });

    await flushPromises();
    expect(() => wrapper.unmount()).not.toThrow();
  });
});
