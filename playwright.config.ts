import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against an already-running stack:
 *
 *   docker compose up -d --build
 *   pnpm test:e2e
 *
 * Playwright does not start the services itself, because the suite must exercise
 * the real containers (API, worker, image worker) rather than a dev server.
 * Provider calls stay disabled: the stack runs with PROVIDER_MODE=fake.
 */
const webBaseUrl = process.env.E2E_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",

  use: {
    baseURL: webBaseUrl,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
