/* eslint-disable no-console */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";


const BASE_URL = process.env.BASE_URL || "http://localhost:3300";
const OUTPUT_DIR = path.resolve(process.cwd(), "docs/assets/screenshots");

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function capture() {
  console.log(`Starting Playwright browser session against ${BASE_URL}...`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // 2x Retina resolution for ultra-sharp presentation
  });

  const page = await context.newPage();

  // Login first so all views have authenticated session and state
  console.log("Logging in as dev owner...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "dev-owner@example.invalid");
  await page.fill('input[type="password"]', "dev-only-insecure-password-change-me");
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1000);

  // 1. Dashboard Overview with active workflows
  console.log("Capturing 01_dashboard.png...");
  await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "01_dashboard.png"),
    fullPage: false,
  });

  // 2. Gate 1 Concept & Idea Research
  console.log("Capturing 02_gate1_idea_research.png...");
  await page.goto(`${BASE_URL}/workflow/00000000-0000-4000-8000-000000000010?tab=concepts`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "02_gate1_idea_research.png"),
    fullPage: false,
  });

  // 3. Gate 2 Artwork Generation & Comparison Gallery
  console.log("Capturing 03_gate2_artwork_gallery.png...");
  await page.goto(`${BASE_URL}/workflow/00000000-0000-4000-8000-000000000020?tab=artwork`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "03_gate2_artwork_gallery.png"),
    fullPage: false,
  });

  // 4. Phase 7 Master PNG & Production Mockup Compositor
  console.log("Capturing 04_phase7_production_mockups.png...");
  await page.goto(`${BASE_URL}/workflow/00000000-0000-4000-8000-000000000099?tab=production`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "04_phase7_production_mockups.png"),
    fullPage: false,
  });

  // 5. Phase 8 Listing SEO, Trademark Screening & Package (Showcase Workflow at Gate 3)
  console.log("Capturing 05_phase8_listing_gate3.png...");
  await page.goto(`${BASE_URL}/workflow/00000000-0000-4000-8000-000000000099?tab=listing`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "05_phase8_listing_gate3.png"),
    fullPage: false,
  });

  // 6. Mockup Template Library
  console.log("Capturing 06_mockup_templates.png...");
  await page.goto(`${BASE_URL}/library`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "06_mockup_templates.png"),
    fullPage: false,
  });

  // 7. Usage & Cost Accounting Ledger
  console.log("Capturing 07_usage_and_costs.png...");
  await page.goto(`${BASE_URL}/usage`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "07_usage_and_costs.png"),
    fullPage: false,
  });

  // 8. Settings Page & Etsy OAuth Connection Card
  console.log("Capturing 08_settings_etsy_oauth.png...");
  await page.goto(`${BASE_URL}/settings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, "08_settings_etsy_oauth.png"),
    fullPage: false,
  });

  await browser.close();
  console.log("All 8 showcase screenshots captured successfully in docs/assets/screenshots/!");
}

capture().catch((err) => {
  console.error("Screenshot capture failed:", err);
  process.exit(1);
});
