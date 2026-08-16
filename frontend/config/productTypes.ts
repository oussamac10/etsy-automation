export interface ProductTypeOption {
  value: string;
  label: string;
  icon: string;
  isCustom?: boolean;
}

export const STANDARD_PRODUCT_TYPES: ProductTypeOption[] = [
  { value: "mug", label: "Ceramic Mug", icon: "lucide:coffee" },
  { value: "tshirt", label: "T-Shirt", icon: "lucide:shirt" },
  { value: "sweatshirt", label: "Sweatshirt / Hoodie", icon: "lucide:shirt" },
  { value: "tote_bag", label: "Tote Bag", icon: "lucide:shopping-bag" },
  { value: "tumbler", label: "Tumbler / Cup", icon: "lucide:cup-soda" },
  { value: "poster", label: "Poster / Wall Art", icon: "lucide:image" },
  { value: "sticker", label: "Stickers", icon: "lucide:tags" },
  { value: "phone_case", label: "Phone Case", icon: "lucide:smartphone" },
  { value: "candle", label: "Scented Candle", icon: "lucide:flame" },
];

export function getProductLabel(val: string): string {
  const found = STANDARD_PRODUCT_TYPES.find(
    (p) => p.value === val || p.value === val.toLowerCase().replace(/[\s-]+/g, "_")
  );
  if (found) return found.label;
  return val
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getProductIconName(val: string): string {
  const found = STANDARD_PRODUCT_TYPES.find(
    (p) => p.value === val || p.value === val.toLowerCase().replace(/[\s-]+/g, "_")
  );
  if (found) return found.icon;
  return "lucide:package";
}

const STANDARD_ALIASES: Record<string, string> = {
  "tshirt": "tshirt",
  "t-shirt": "tshirt",
  "t_shirt": "tshirt",
  "tee": "tshirt",
  "shirt": "tshirt",
  "sweatshirt": "sweatshirt",
  "sweat-shirt": "sweatshirt",
  "sweat_shirt": "sweatshirt",
  "hoodie": "sweatshirt",
  "crewneck": "sweatshirt",
  "tote_bag": "tote_bag",
  "tote": "tote_bag",
  "tote-bag": "tote_bag",
  "canvas_tote": "tote_bag",
  "mug": "mug",
  "ceramic_mug": "mug",
  "coffee_mug": "mug",
  "cup": "mug",
  "tumbler": "tumbler",
  "tumblers": "tumbler",
  "poster": "poster",
  "posters": "poster",
  "wall_art": "poster",
  "sticker": "sticker",
  "stickers": "sticker",
  "phone_case": "phone_case",
  "phone": "phone_case",
  "candle": "candle",
  "candles": "candle",
  "scented_candle": "candle",
};

export function normalizeProductKey(raw?: string | null): string {
  if (!raw) return "product";
  const slug = raw.toLowerCase().trim().replace(/[\s\-\/]+/g, "_").replace(/^_+|_+$/g, "");
  return STANDARD_ALIASES[slug] || slug;
}
