import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import PricingInventoryCard from '../components/workflow/listing/PricingInventoryCard.vue';
import ShopOrganizationCard from '../components/workflow/listing/ShopOrganizationCard.vue';
import TaxonomyAttributesCard from '../components/workflow/listing/TaxonomyAttributesCard.vue';
import EtsyListingDefaultsCard from '../components/settings/EtsyListingDefaultsCard.vue';

// Mock Nuxt globals
vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBase: 'http://localhost:8000',
  },
}));

describe('Phase 9 Listing Automation Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('PricingInventoryCard', () => {
    it('renders price, quantity, and SKU inputs', async () => {
      vi.stubGlobal(
        '$fetch',
        vi.fn().mockResolvedValue({
          recommended_minor_units: 549,
          currency: 'USD',
          formatted_price: '$5.49',
          rationale: 'High seasonal holiday demand (+0.50)',
          factors: ['Standard 4500x5400 Master PNG', 'High seasonal holiday demand'],
        })
      );

      const wrapper = mount(PricingInventoryCard, {
        props: {
          workflowId: 'wf-100',
          priceMinorUnits: 499,
          currency: 'USD',
          quantity: 999,
          sku: 'NCP-RETRO-XMAS-001',
          isSaving: false,
        },
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      const priceInput = wrapper.find('#listing-price');
      expect(priceInput.exists()).toBe(true);
      expect((priceInput.element as HTMLInputElement).value).toBe('4.99');

      const qtyInput = wrapper.find('#listing-quantity');
      expect((qtyInput.element as HTMLInputElement).value).toBe('999');

      const skuInput = wrapper.find('#listing-sku');
      expect((skuInput.element as HTMLInputElement).value).toBe('NCP-RETRO-XMAS-001');

      // Verify recommendation banner is displayed
      expect(wrapper.text()).toContain('Smart Recommended Price: $5.49');
      expect(wrapper.text()).toContain('High seasonal holiday demand');
    });

    it('applies recommendation price and currency on click', async () => {
      vi.stubGlobal(
        '$fetch',
        vi.fn().mockResolvedValue({
          recommended_minor_units: 599,
          currency: 'EUR',
          formatted_price: '€5.99',
          rationale: 'Bundle collection',
          factors: ['Multi-design bundle'],
        })
      );

      const wrapper = mount(PricingInventoryCard, {
        props: {
          workflowId: 'wf-100',
          priceMinorUnits: 499,
          currency: 'USD',
          quantity: 999,
          sku: 'NCP-RETRO-XMAS-001',
        },
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      const useRecBtn = wrapper.findAll('button').find((b) => b.text().includes('Use recommendation'));
      expect(useRecBtn).toBeDefined();
      await useRecBtn?.trigger('click');

      expect(wrapper.emitted('update:priceMinorUnits')?.[0]).toEqual([599]);
      expect(wrapper.emitted('update:currency')?.[0]).toEqual(['EUR']);
    });
  });

  describe('ShopOrganizationCard', () => {
    it('renders section selector and renewal mode options', async () => {
      vi.stubGlobal(
        '$fetch',
        vi.fn().mockResolvedValue([
          { shop_section_id: 'sec-1', title: 'Christmas PNGs', rank: 1, active_listing_count: 8 },
          { shop_section_id: 'sec-2', title: 'Sublimation Bundles', rank: 2, active_listing_count: 14 },
        ])
      );

      const wrapper = mount(ShopOrganizationCard, {
        props: {
          workflowId: 'wf-100',
          shopSectionId: 'sec-1',
          shopSectionName: 'Christmas PNGs',
          shouldAutoRenew: false,
        },
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Christmas PNGs');
      expect(wrapper.text()).toContain('Sublimation Bundles');
      expect(wrapper.text()).toContain('Manual Renewal');
      expect(wrapper.text()).toContain('Automatic Renewal');
    });

    it('emits auto renewal change when clicked', async () => {
      vi.stubGlobal('$fetch', vi.fn().mockResolvedValue([]));

      const wrapper = mount(ShopOrganizationCard, {
        props: {
          workflowId: 'wf-100',
          shopSectionId: null,
          shouldAutoRenew: false,
        },
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      const autoBtn = wrapper.findAll('button').find((b) => b.text().includes('Automatic Renewal'));
      expect(autoBtn).toBeDefined();
      await autoBtn?.trigger('click');

      expect(wrapper.emitted('update:shouldAutoRenew')?.[0]).toEqual([true]);
    });
  });

  describe('TaxonomyAttributesCard', () => {
    it('renders dynamic properties and toggles selections', async () => {
      vi.stubGlobal(
        '$fetch',
        vi.fn().mockResolvedValue([
          {
            property_id: 513,
            name: 'Craft type',
            is_required: false,
            is_multivalued: true,
            possible_values: [
              { value_id: 101, name: 'Sublimation' },
              { value_id: 102, name: 'Printing' },
            ],
            suggested_value_ids: [101],
            suggested_values: ['Sublimation'],
          },
        ])
      );

      const wrapper = mount(TaxonomyAttributesCard, {
        props: {
          workflowId: 'wf-100',
          taxonomyId: 6844,
          etsyProperties: {
            '513': { property_id: 513, value_ids: [101], values: ['Sublimation'] },
          },
        },
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Craft type');
      expect(wrapper.text()).toContain('Sublimation');
      expect(wrapper.text()).toContain('Printing');

      // Click on "Printing" to multi-select
      const printingBtn = wrapper.findAll('button').find((b) => b.text().includes('Printing'));
      expect(printingBtn).toBeDefined();
      await printingBtn?.trigger('click');

      const emitted = wrapper.emitted('update:etsyProperties');
      expect(emitted).toBeDefined();
      const updatedProps = emitted?.[emitted.length - 1][0] as Record<string, any>;
      expect(updatedProps['513'].values).toContain('Printing');
      expect(updatedProps['513'].values).toContain('Sublimation');
    });
  });

  describe('EtsyListingDefaultsCard', () => {
    it('loads and displays owner listing defaults', async () => {
      vi.stubGlobal(
        '$fetch',
        vi.fn().mockResolvedValue({
          default_digital_price_minor: 499,
          default_digital_quantity: 999,
          default_auto_renew: true,
          default_shop_section_strategy: 'match_niche',
        })
      );

      const wrapper = mount(EtsyListingDefaultsCard, {
        global: {
          stubs: {
            Icon: { template: '<i />' },
          },
        },
      });

      await flushPromises();

      expect((wrapper.find('#default-price').element as HTMLInputElement).value).toBe('4.99');
      expect((wrapper.find('#default-quantity').element as HTMLInputElement).value).toBe('999');
      expect(wrapper.text()).toContain('Automatic');
    });
  });
});
