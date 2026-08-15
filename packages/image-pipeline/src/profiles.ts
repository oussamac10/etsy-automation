export interface PrintProfile {
  readonly name: string;
  readonly canvasWidth: number;
  readonly canvasHeight: number;
  readonly densityDpi: number;
  readonly format: "png";
  readonly colorSpace: "sRGB";
  readonly background: "transparent";
  readonly defaultMarginPercent: number;
}

export const PRINT_PROFILES = {
  "etsy-png-standard": {
    name: "etsy-png-standard",
    canvasWidth: 4500,
    canvasHeight: 5400,
    densityDpi: 300,
    format: "png",
    colorSpace: "sRGB",
    background: "transparent",
    defaultMarginPercent: 8,
  },
} as const satisfies Record<string, PrintProfile>;

export type PrintProfileName = keyof typeof PRINT_PROFILES;

export const DEFAULT_PRINT_PROFILE: PrintProfile = PRINT_PROFILES["etsy-png-standard"];
