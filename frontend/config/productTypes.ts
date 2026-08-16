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

export function normalizeProductKey(raw?: string | null): string {
  if (!raw) return "product";
  const text = raw.toLowerCase().trim();
  if (text.includes("tumbler") || text === "tumblers") return "tumbler";
  if (text.includes("mug") || text.includes("ceramic") || text === "mug" || text === "cup") return "mug";
  if (text.includes("sweat") || text.includes("hoodie") || text.includes("crewneck") || text === "sweatshirt") return "sweatshirt";
  if (text.includes("tote") || text.includes("bag") || text === "tote_bag") return "tote_bag";
  if (text.includes("shirt") || text.includes("tee") || text.includes("apparel") || text === "tshirt") return "tshirt";
  if (text.includes("poster") || text.includes("wall_art")) return "poster";
  if (text.includes("sticker") || text.includes("stickers")) return "sticker";
  if (text.includes("phone")) return "phone_case";
  if (text.includes("candle") || text.includes("candles")) return "candle";
  return text.replace(/\s+/g, "_").replace(/-/g, "_");
}
