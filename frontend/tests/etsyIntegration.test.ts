import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import EtsyConnectionCard from '../components/settings/EtsyConnectionCard.vue';
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
  etsy_listing_id: null,
  etsy_image_ids: [],
  etsy_file_id: null,
  etsy_dispatch_status: 'not_started',
};

describe('Etsy Frontend Integration Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('useEtsy Composable', () => {
    it('fetches connection status', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        connected: true,
        shop_id: 'shop-777',
        shop_name: 'MoonlightStudio',
        connection_status: 'connected',
        granted_scopes: ['listings_w', 'shops_r'],
        token_health: 'valid',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const { fetchConnectionStatus, connectionStatus } = useEtsy();
      const status = await fetchConnectionStatus();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/integrations/etsy'),
        expect.anything()
      );
      expect(status?.connected).toBe(true);
      expect(connectionStatus.value?.shop_name).toBe('MoonlightStudio');
    });

    it('triggers draft creation', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        workflow_id: 'wf-123',
        dispatch_status: 'queued',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const { triggerCreateEtsyDraft, draftStatus } = useEtsy();
      const resp = await triggerCreateEtsyDraft('wf-123');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/workflows/wf-123/etsy/draft'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(resp?.dispatch_status).toBe('queued');
      expect(draftStatus.value?.dispatch_status).toBe('queued');
    });
  });

  describe('EtsyConnectionCard Component', () => {
    it('renders disconnected state and connect button', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        connected: false,
        connection_status: 'disconnected',
        granted_scopes: [],
        token_health: 'disconnected',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const wrapper = mount(EtsyConnectionCard, {
        global: {
          stubs: {
            Icon: true,
            NuxtLink: true,
          },
        },
      });

      await flushPromises();

      expect(wrapper.find('[data-testid="etsy-status-disconnected"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="etsy-connect-button"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Connect Etsy Shop');
    });

    it('renders connected state with shop details and disconnect button', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        connected: true,
        shop_id: 'shop-888',
        shop_name: 'StarlightCrafts',
        connection_status: 'connected',
        granted_scopes: ['listings_w', 'shops_r'],
        token_health: 'valid',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const wrapper = mount(EtsyConnectionCard, {
        global: {
          stubs: {
            Icon: true,
            NuxtLink: true,
          },
        },
      });

      await flushPromises();

      expect(wrapper.find('[data-testid="etsy-status-connected"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('StarlightCrafts');
      expect(wrapper.text()).toContain('shop-888');
      expect(wrapper.find('[data-testid="etsy-disconnect-button"]').exists()).toBe(true);
    });
  });

  describe('EtsyDraftCard Component', () => {
    it('renders ready state with create draft button', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        connected: true,
        shop_id: 'shop-888',
        shop_name: 'StarlightCrafts',
        connection_status: 'connected',
        granted_scopes: ['listings_w'],
        token_health: 'valid',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const wrapper = mount(EtsyDraftCard, {
        props: {
          workflowId: 'wf-123',
          workflowState: 'READY_FOR_ETSY_DRAFT',
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

      expect(wrapper.find('[data-testid="etsy-badge-ready"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="etsy-create-draft-btn"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Create Etsy Draft');
    });

    it('renders completed card with listing ID and link to Etsy Shop Manager', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        connected: true,
        shop_id: 'shop-888',
        shop_name: 'StarlightCrafts',
        connection_status: 'connected',
        granted_scopes: ['listings_w'],
        token_health: 'valid',
      });
      vi.stubGlobal('$fetch', fetchMock);

      const completedListing: ListingDraft = {
        ...mockListing,
        etsy_listing_id: '9988776655',
        etsy_shop_id: 'shop-888',
        etsy_state: 'draft',
        etsy_image_ids: ['img-1', 'img-2', 'img-3'],
        etsy_file_id: 'file-1',
        etsy_dispatch_status: 'completed',
      };

      const wrapper = mount(EtsyDraftCard, {
        props: {
          workflowId: 'wf-123',
          workflowState: 'ETSY_DRAFT_CREATED',
          listing: completedListing,
        },
        global: {
          stubs: {
            Icon: true,
            NuxtLink: true,
          },
        },
      });

      await flushPromises();

      expect(wrapper.find('[data-testid="etsy-badge-completed"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('9988776655');
      expect(wrapper.text()).toContain('3 Mockups');
      expect(wrapper.text()).toContain('Digital Product Attached');
      expect(wrapper.find('[data-testid="etsy-open-manager-btn"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Open in Etsy Shop Manager');
    });
  });
});
