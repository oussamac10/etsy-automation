import { ref, computed } from "vue";
import {
  STANDARD_PRODUCT_TYPES,
  getProductLabel,
  getProductIconName,
  normalizeProductKey,
  type ProductTypeOption,
} from "~/config/productTypes";

export interface LibraryProductOption extends ProductTypeOption {
  templateCount?: number;
}

export function useLibraryProducts() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase || "http://localhost:8800";

  const templates = ref<Array<{ id: string; product_type: string }>>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  async function fetchLibraryProducts(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const data = await $fetch<Array<{ id: string; product_type: string }>>(
        `${apiBase.replace(/\/$/, "")}/api/v1/mockup-templates`,
        { credentials: "include" }
      );
      templates.value = data || [];
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "Failed to load library products";
    } finally {
      isLoading.value = false;
    }
  }

  const libraryProductOptions = computed<LibraryProductOption[]>(() => {
    const map = new Map<string, LibraryProductOption>();

    // 1. Add all standard product types
    for (const std of STANDARD_PRODUCT_TYPES) {
      map.set(std.value, {
        ...std,
        templateCount: 0,
      });
    }

    // 2. Count templates and register any custom categories from library
    for (const t of templates.value) {
      const norm = normalizeProductKey(t.product_type);
      if (!map.has(norm)) {
        map.set(norm, {
          value: norm,
          label: getProductLabel(norm),
          icon: getProductIconName(norm),
          isCustom: true,
          templateCount: 1,
        });
      } else {
        const item = map.get(norm)!;
        item.templateCount = (item.templateCount || 0) + 1;
      }
    }

    return Array.from(map.values());
  });

  return {
    templates,
    isLoading,
    error,
    fetchLibraryProducts,
    libraryProductOptions,
  };
}
