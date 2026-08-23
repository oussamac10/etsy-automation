 
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE_URL = process.env.BASE_URL || "http://localhost:3300";
const OUTPUT_DIR = path.resolve(process.cwd(), "docs/assets/screenshots");

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function capture() {
  console.warn(`Starting Playwright browser session against ${BASE_URL}...`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // 2x Retina resolution for ultra-sharp presentation
  });

  const page = await context.newPage();

  // Login as real user chajiioussama254@gmail.com
  console.warn("Logging in as real user chajiioussama254@gmail.com...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "chajiioussama254@gmail.com");
  await page.fill('input[type="password"]', "dev-only-insecure-password-change-me");
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1500);

  // 1. Dashboard Overview with real active and completed campaigns
  console.warn("Capturing 01_dashboard.png...");
  await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "01_dashboard.png"),
    fullPage: false,
  });

  // 2. Gate 1 Concept & Idea Research (Real campaign: Cozy Book Lover Ghost / Tactile Bear)
  console.warn("Capturing 02_gate1_idea_research.png...");
  await page.goto(`${BASE_URL}/workflow/daf80ad8-aa5a-4e6d-913d-46be6da13cea?tab=concepts`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "02_gate1_idea_research.png"),
    fullPage: false,
  });

  // 3. Gate 2 Artwork Generation & Comparison Gallery (Real campaign: Floral Classroom Coffee Pot / Woodland Bear)
  console.warn("Capturing 03_gate2_artwork_gallery.png...");
  await page.goto(`${BASE_URL}/workflow/dcbf7a2c-c12b-40bb-add7-67cd463bad66?tab=artwork`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "03_gate2_artwork_gallery.png"),
    fullPage: false,
  });

  // 4. Phase 7 Master PNG & Production Mockup Gallery (Real campaign: Vibrant Teal & Magenta Floral Skull Monarch)
  console.warn("Capturing 04_phase7_production_mockups.png...");
  await page.goto(`${BASE_URL}/workflow/e3f30575-7cfd-4cbd-8f6e-8c98b20f4f2c?tab=production`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "04_phase7_production_mockups.png"),
    fullPage: false,
  });

  // 5. Phase 8 Listing SEO, Trademark Screening & Package (Real campaign: Highland Cow Teacher Back to School Calf)
  console.warn("Capturing 05_phase8_listing_gate3.png...");
  await page.goto(`${BASE_URL}/workflow/404e19dd-9153-48ae-81f6-e7725520a8c7?tab=listing`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "05_phase8_listing_gate3.png"),
    fullPage: false,
  });

  // 6. Mockup Template Library
  console.warn("Capturing 06_mockup_templates.png...");
  await page.goto(`${BASE_URL}/library`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "06_mockup_templates.png"),
    fullPage: false,
  });

  // 7. Usage & Cost Accounting Ledger
  console.warn("Capturing 07_usage_and_costs.png...");
  await page.goto(`${BASE_URL}/usage`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "07_usage_and_costs.png"),
    fullPage: false,
  });

  // 8. Settings Page & Etsy OAuth Connection Card
  console.warn("Capturing 08_settings_etsy_oauth.png...");
  await page.goto(`${BASE_URL}/settings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "08_settings_etsy_oauth.png"),
    fullPage: false,
  });

  await browser.close();
  console.warn("All 8 real campaign showcase screenshots captured successfully in docs/assets/screenshots/!");
}

capture().catch((err) => {
  console.error("Screenshot capture failed:", err);
  process.exit(1);
});
