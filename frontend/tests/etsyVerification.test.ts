import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import EtsyDraftVerificationCard from '../components/workflow/listing/EtsyDraftVerificationCard.vue';
import EtsyDraftCard from '../components/workflow/listing/EtsyDraftCard.vue';
import type { EtsyDraftVerification } from '../types/etsy';
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

const mockVerifiedPayload: EtsyDraftVerification = {
  workflow_id: 'wf-101',
  listing_id: '4559404921',
  status: 'verified',
  verified_at: '2026-08-20T14:30:00Z',
  summary: {
    synced: 12,
    warnings: 0,
    errors: 0,
    manual_review: 3,
    total: 15,
  },
  checks: [
    {
      key: 'title',
      label: 'Listing Title',
      category: 'listing',
      status: 'synced',
      expected: 'Cozy Fall Book Lover PNG Digital Download',
      actual: 'Cozy Fall Book Lover PNG Digital Download',
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'taxonomy',
      label: 'Seller Taxonomy / Category',
      category: 'listing',
      status: 'synced',
      expected: '77 — Art & Collectibles > Drawing & Illustration > Digital',
      actual: '77 — Art & Collectibles > Drawing & Illustration > Digital',
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'price',
      label: 'Listing Price & Currency',
      category: 'commerce',
      status: 'synced',
      expected: '4.99 EUR',
      actual: '4.99 EUR',
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'quantity',
      label: 'Stock Quantity',
      category: 'commerce',
      status: 'synced',
      expected: 999,
      actual: 999,
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'sku',
      label: 'SKU Identifier',
      category: 'commerce',
      status: 'synced',
      expected: 'NCP-COZY-FALL-6125',
      actual: 'NCP-COZY-FALL-6125',
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'mockups',
      label: 'Mockup Images Uploaded',
      category: 'media_and_delivery',
      status: 'synced',
      expected: '4 mockups',
      actual: '4 mockups on Etsy',
      message: null,
      source: 'etsy_api',
    },
    {
      key: 'digital_files',
      label: 'Customer Deliverables (Digital Files)',
      category: 'media_and_delivery',
      status: 'synced',
      expected: '2 files',
      actual: '2 files on Etsy',
      message: null,
      source: 'etsy_api',
      details: {
        actual_filenames: ['cozy_fall_master.png', 'cozy_fall_extras.zip'],
      },
    },
    {
      key: 'ai_disclosure',
      label: 'AI Creation Disclosure',
      category: 'manual_review',
      status: 'manual_review',
      expected: 'Generated with AI',
      actual: 'Manual check',
      message: 'Confirm "Created with AI generator" is checked in Etsy Shop Manager.',
      source: 'manual_review',
    },
    {
      key: 'shopping_cart_summary',
      label: 'Shopping Cart Summary',
      category: 'manual_review',
      status: 'manual_review',
      expected: 'Cozy Fall Book Lover PNG Sublimation Graphic',
      actual: 'Manual copy',
      message: 'Copy pre-formatted summary text to Etsy web editor.',
      source: 'manual_review',
      details: {
        copy_ready_text: 'Cozy Fall Book Lover PNG Sublimation Graphic',
      },
    },
  ],
};

const mockNeedsAttentionPayload: EtsyDraftVerification = {
  workflow_id: 'wf-101',
  listing_id: '4559404921',
  status: 'needs_attention',
  verified_at: '2026-08-20T14:35:00Z',
  summary: {
    synced: 10,
    warnings: 2,
    errors: 0,
    manual_review: 3,
    total: 15,
  },
  checks: [
    {
      key: 'title',
      label: 'Listing Title',
      category: 'listing',
      status: 'different',
      expected: 'Cozy Fall Book Lover PNG Digital Download',
      actual: 'Modified Title on Etsy Shop Manager',
      message: 'Local title differs from live Etsy draft title.',
      source: 'etsy_api',
    },
    {
      key: 'digital_files',
      label: 'Customer Deliverables (Digital Files)',
      category: 'media_and_delivery',
      status: 'missing',
      expected: '2 files',
      actual: '0 files on Etsy',
      message: 'Digital files have not been uploaded to Etsy yet.',
      source: 'etsy_api',
    },
  ],
};

describe('Post-Dispatch Etsy Draft Verification UI Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders verified state with manual review count badge and stats cards', () => {
    const wrapper = mount(EtsyDraftVerificationCard, {
      props: {
        workflowId: 'wf-101',
        listingId: '4559404921',
        verification: mockVerifiedPayload,
        shopManagerUrl: 'https://www.etsy.com/your/shops/me/listing-editor/edit/4559404921',
      },
      global: {
        stubs: {
          Icon: { template: '<span class="icon-stub"><slot /></span>' },
        },
      },
    });

    expect(wrapper.find('[data-testid="etsy-verification-card"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="verification-status-badge"]').text()).toContain('Verified');
    expect(wrapper.find('[data-testid="verification-status-badge"]').text()).toContain('3 manual checks');

    expect(wrapper.text()).toContain('12 Synced');
    expect(wrapper.text()).toContain('3 Manual Checks');
    expect(wrapper.text()).toContain('15 Total Checks');
  });

  it('renders needs_attention state with warning indicators and difference messages', () => {
    const wrapper = mount(EtsyDraftVerificationCard, {
      props: {
        workflowId: 'wf-101',
        listingId: '4559404921',
        verification: mockNeedsAttentionPayload,
      },
      global: {
        stubs: {
          Icon: { template: '<span class="icon-stub"><slot /></span>' },
        },
      },
    });

    expect(wrapper.find('[data-testid="verification-status-badge"]').text()).toContain('Needs Attention');
    expect(wrapper.text()).toContain('Local title differs from live Etsy draft title.');
    expect(wrapper.text()).toContain('Digital files have not been uploaded to Etsy yet.');
  });

  it('copies shopping cart summary text when copy button is clicked', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    });

    const wrapper = mount(EtsyDraftVerificationCard, {
      props: {
        workflowId: 'wf-101',
        listingId: '4559404921',
        verification: mockVerifiedPayload,
      },
      global: {
        stubs: {
          Icon: { template: '<span class="icon-stub"><slot /></span>' },
        },
      },
    });

    const copyBtn = wrapper.find('[data-testid="copy-cart-summary-btn"]');
    expect(copyBtn.exists()).toBe(true);

    await copyBtn.trigger('click');
    expect(writeTextMock).toHaveBeenCalledWith('Cozy Fall Book Lover PNG Sublimation Graphic');
  });

  it('triggers re-check API endpoint when Re-check Etsy button is clicked', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockVerifiedPayload);
    vi.stubGlobal('$fetch', fetchMock);

    const wrapper = mount(EtsyDraftVerificationCard, {
      props: {
        workflowId: 'wf-101',
        listingId: '4559404921',
        verification: mockNeedsAttentionPayload,
      },
      global: {
        stubs: {
          Icon: { template: '<span class="icon-stub"><slot /></span>' },
        },
      },
    });

    const recheckBtn = wrapper.find('[data-testid="etsy-recheck-btn"]');
    expect(recheckBtn.exists()).toBe(true);

    await recheckBtn.trigger('click');
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/v1/workflows/wf-101/etsy/verify', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
      },
      credentials: 'include',
    });
    expect(wrapper.emitted('recheck-completed')).toBeTruthy();
  });

  it('embeds verification card in EtsyDraftCard when draft is completed', async () => {
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

    const mockListing: ListingDraft = {
      id: 'draft-101',
      workflow_id: 'wf-101',
      title: 'Cozy Fall Book Lover PNG',
      description: 'High res PNG.',
      tags: ['fall png'],
      price_minor_units: 499,
      currency: 'USD',
      taxonomy_id: 77,
      ip_risk_level: 'low',
      ip_findings: {},
      version: 1,
      etsy_listing_id: '4559404921',
      etsy_dispatch_status: 'completed',
      etsy_image_ids: ['img-1', 'img-2', 'img-3', 'img-4'],
      etsy_file_ids: ['f-1', 'f-2'],
      etsy_verification_status: 'verified',
      etsy_verification_result: mockVerifiedPayload,
    };

    const wrapper = mount(EtsyDraftCard, {
      props: {
        workflowId: 'wf-101',
        workflowState: 'ETSY_DRAFT_CREATED',
        listing: mockListing,
      },
      global: {
        stubs: {
          Icon: { template: '<span class="icon-stub"><slot /></span>' },
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="etsy-completed-panel"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="etsy-verification-card"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="verification-status-badge"]').text()).toContain('Verified');
  });
});
