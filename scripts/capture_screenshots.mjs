import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE_URL = process.env.BASE_URL || "http://localhost:3300";
const WORKFLOW_ID = "e3f30575-7cfd-4cbd-8f6e-8c98b20f4f2c";
const OUTPUT_DIR = path.resolve(process.cwd(), "docs/assets/screenshots");

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // 2x Retina resolution for ultra-sharp presentation
  });

  const page = await context.newPage();

  // Login as real user chajiioussama254@gmail.com
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "chajiioussama254@gmail.com");
  await page.fill('input[type="password"]', "dev-only-insecure-password-change-me");
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1500);

  // 1. Dashboard Overview showing real workflow campaigns
  await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "01_dashboard.png"),
    fullPage: false,
  });

  // 2. Gate 1: Concept & Market Opportunity Discovery (Same campaign: Vibrant Teal & Magenta Floral Skull Monarch)
  await page.goto(`${BASE_URL}/workflow/${WORKFLOW_ID}?tab=concepts`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "02_gate1_idea_research.png"),
    fullPage: false,
  });

  // 3. Gate 2: Artwork Studio & Candidate PNGs (Same campaign: Vibrant Teal & Magenta Floral Skull Monarch)
  await page.goto(`${BASE_URL}/workflow/${WORKFLOW_ID}?tab=artwork`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "03_gate2_artwork_gallery.png"),
    fullPage: false,
  });

  // 4. Phase 7: Print-Ready 4500x5400 Master PNG & QA (Same campaign: Vibrant Teal & Magenta Floral Skull Monarch)
  await page.goto(`${BASE_URL}/workflow/${WORKFLOW_ID}?tab=production`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "04_phase7_production_mockups.png"),
    fullPage: false,
  });

  // 5. Gate 3: Listing SEO, 13 Tags, Trademark & Customer ZIP (Same campaign: Vibrant Teal & Magenta Floral Skull Monarch)
  await page.goto(`${BASE_URL}/workflow/${WORKFLOW_ID}?tab=listing`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "05_phase8_listing_gate3.png"),
    fullPage: false,
  });

  // 6. Mockup Template Library
  await page.goto(`${BASE_URL}/library`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "06_mockup_templates.png"),
    fullPage: false,
  });

  // 7. Usage & Cost Accounting Ledger
  await page.goto(`${BASE_URL}/usage`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "07_usage_and_costs.png"),
    fullPage: false,
  });

  // 8. Settings Page & Etsy OAuth Connection Card
  await page.goto(`${BASE_URL}/settings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "08_settings_etsy_oauth.png"),
    fullPage: false,
  });

  await browser.close();
}

capture().catch((err) => {
   
  console.error("Screenshot capture failed:", err);
  process.exit(1);
});
