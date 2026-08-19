/**
 * Centralized product mapping, placement presets, and icon utilities for mockups.
 */

import { icons } from "~/config/icons";

export interface BlendModeOption {
  value: "over" | "overlay" | "soft-light" | "multiply" | "screen" | "darken" | "lighten";
  label: string;
  shortLabel: string;
  badge: string;
  badgeVariant?: "default" | "secondary" | "outline" | "success" | "warning";
  description: string;
  bestFor: string;
  iconName: string;
}

export const BLEND_MODE_OPTIONS: BlendModeOption[] = [
  {
    value: "over",
    label: "Solid / Opaque (Direct-to-Garment)",
    shortLabel: "Solid / Opaque",
    badge: "Crisp & True Colors",
    description: "100% true vibrant colors without darkening. Preserves crisp white text on black/dark shirts, mugs, stickers, and canvas.",
    bestFor: "Dark/Colored Shirts, Mugs, Posters, Crisp White Text",
    iconName: "lucide:layers",
  },
  {
    value: "overlay",
    label: "Overlay (Vibrant Fabric Integration)",
    shortLabel: "Overlay",
    badge: "Balanced & Vivid",
    description: "Natural fabric texture and folds show through while preserving bright highlights and vivid colors.",
    bestFor: "Colored Fabrics, Graphic Tees, High Contrast Designs",
    iconName: "lucide:sparkles",
  },
  {
    value: "soft-light",
    label: "Soft Light (Subtle Realism)",
    shortLabel: "Soft Light",
    badge: "Soft & Natural",
    description: "Softly diffuses fabric shadows and lighting into the graphic without heavily darkening midtones.",
    bestFor: "Pastel Shirts, Heather Fabrics, Soft Prints",
    iconName: "lucide:sun",
  },
  {
    value: "multiply",
    label: "Multiply (Apparel Shadow / Sublimation)",
    shortLabel: "Multiply",
    badge: "Vintage Sublimation",
    description: "Ink embeds deeply into fabric fibers. Folds and shadows pass through completely (darkens colors).",
    bestFor: "White / Light Heather Shirts (Avoid if design has white text)",
    iconName: "lucide:blend",
  },
  {
    value: "screen",
    label: "Screen (Light / Neon Graphics)",
    shortLabel: "Screen",
    badge: "Luminous & Glow",
    description: "Only bright pixels blend onto the mockup while dark backgrounds turn transparent.",
    bestFor: "Dark / Black Backgrounds, Neon & Luminous Art",
    iconName: "lucide:sun-medium",
  },
  {
    value: "darken",
    label: "Darken (Deep Inks)",
    shortLabel: "Darken",
    badge: "Deep Contrast",
    description: "Keeps only design pixels that are darker than the underlying garment texture.",
    bestFor: "Black Linework, Typographic Quotes",
    iconName: "lucide:moon",
  },
];

export function getBlendModeInfo(mode?: string | null): BlendModeOption {
  const norm = (mode || "over").toLowerCase().trim().replace(/_/g, "-");
  return BLEND_MODE_OPTIONS.find((b) => b.value === norm) || BLEND_MODE_OPTIONS[0];
}

export interface MockupProductPreset {
  key: string;
  label: string;
  icon: string;
  defaultPlacement: {
    left_pct: number;
    top_pct: number;
    width_pct: number;
    height_pct: number;
    angle_deg: number;
    blend_mode: "multiply" | "over" | "screen" | "overlay" | "soft-light" | "darken" | "lighten" | string;
  };
}

export const PRODUCT_PRESETS: Record<string, MockupProductPreset> = {
  tshirt: {
    key: "tshirt",
    label: "T-Shirt",
    icon: icons.tshirt,
    defaultPlacement: {
      left_pct: 0.28,
      top_pct: 0.25,
      width_pct: 0.44,
      height_pct: 0.48,
      angle_deg: 0,
      blend_mode: "multiply",
    },
  },
  sweatshirt: {
    key: "sweatshirt",
    label: "Sweatshirt",
    icon: icons.sweatshirt,
    defaultPlacement: {
      left_pct: 0.28,
      top_pct: 0.26,
      width_pct: 0.44,
      height_pct: 0.46,
      angle_deg: 0,
      blend_mode: "multiply",
    },
  },
  tote_bag: {
    key: "tote_bag",
    label: "Tote Bag",
    icon: icons.toteBag,
    defaultPlacement: {
      left_pct: 0.26,
      top_pct: 0.36,
      width_pct: 0.48,
      height_pct: 0.46,
      angle_deg: 0,
      blend_mode: "multiply",
    },
  },
  mug: {
    key: "mug",
    label: "Ceramic Mug",
    icon: icons.mug,
    defaultPlacement: {
      left_pct: 0.32,
      top_pct: 0.32,
      width_pct: 0.36,
      height_pct: 0.38,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
  tumbler: {
    key: "tumbler",
    label: "Tumbler",
    icon: icons.tumbler,
    defaultPlacement: {
      left_pct: 0.30,
      top_pct: 0.28,
      width_pct: 0.40,
      height_pct: 0.48,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
  poster: {
    key: "poster",
    label: "Poster",
    icon: icons.poster,
    defaultPlacement: {
      left_pct: 0.20,
      top_pct: 0.20,
      width_pct: 0.60,
      height_pct: 0.60,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
  sticker: {
    key: "sticker",
    label: "Sticker",
    icon: icons.sticker,
    defaultPlacement: {
      left_pct: 0.25,
      top_pct: 0.25,
      width_pct: 0.50,
      height_pct: 0.50,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
  phone_case: {
    key: "phone_case",
    label: "Phone Case",
    icon: icons.phoneCase,
    defaultPlacement: {
      left_pct: 0.28,
      top_pct: 0.22,
      width_pct: 0.44,
      height_pct: 0.56,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
  candle: {
    key: "candle",
    label: "Scented Candle",
    icon: icons.candle,
    defaultPlacement: {
      left_pct: 0.32,
      top_pct: 0.38,
      width_pct: 0.36,
      height_pct: 0.34,
      angle_deg: 0,
      blend_mode: "over",
    },
  },
};

export const SUPPORTED_PRODUCT_TYPES = Object.values(PRODUCT_PRESETS);

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
  const clean = raw.trim().replace(/^['"\[\]\s]+|['"\[\]\s]+$/g, "");
  const slug = clean.toLowerCase().replace(/[\s/-]+/g, "_").replace(/^_+|_+$/g, "");
  return STANDARD_ALIASES[slug] || slug;
}

export function getProductLabel(key: string): string {
  const clean = key.trim().replace(/^['"\[\]\s]+|['"\[\]\s]+$/g, "");
  const norm = normalizeProductKey(clean);
  if (PRODUCT_PRESETS[norm]) {
    return PRODUCT_PRESETS[norm].label;
  }
  return clean
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getProductIconName(key: string): string {
  const norm = normalizeProductKey(key);
  if (PRODUCT_PRESETS[norm]) {
    return PRODUCT_PRESETS[norm].icon;
  }
  return "lucide:package";
}

export function extractProductFromKey(storageKey?: string): string {
  if (!storageKey) return "product";
  const lower = storageKey.toLowerCase();
  for (const preset of SUPPORTED_PRODUCT_TYPES) {
    if (lower.includes(preset.key)) return preset.key;
  }
  return normalizeProductKey(lower.split("/").pop()?.split(".")[0]);
}
