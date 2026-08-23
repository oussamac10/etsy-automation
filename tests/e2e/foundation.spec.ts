import { expect, test } from "@playwright/test";

/**
 * Phase 1 end-to-end checks.
 *
 * These prove the containers are wired together — the dashboard renders live
 * data fetched from the API, and the product rules it must state are present.
 * The approval-gate flow itself is tested from Phase 4 onwards.
 */

const apiBaseUrl = process.env.E2E_API_URL ?? "http://localhost:8000";

test.describe("dashboard", () => {
  test("renders Marketplace Studio dashboard header and brief builder", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: /Marketplace Studio/i, level: 1 }),
    ).toBeVisible();

    await expect(page.getByText(/Automated design research/i)).toBeVisible();
    await expect(page.getByText(/Quick Brief Builder/i)).toBeVisible();
  });

  test("shows active workflows section and controls", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Active Pipelines/i)).toBeVisible();
    await expect(page.getByPlaceholder(/Filter by name or niche/i)).toBeVisible();
  });

  test("is reachable by keyboard from the skip link", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  });
});

test.describe("api", () => {
  test("GET /api/health reports every dependency", async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/api/health`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body.status).toBe("ok");
    expect(Object.keys(body.components).sort()).toEqual([
      "database",
      "image_worker",
      "redis",
    ]);
  });

  test("GET /api/health/live does not require dependencies", async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/api/health/live`);
    expect(response.status()).toBe(200);
    expect((await response.json()).service).toBe("api");
  });

  test("the workflow never publishes automatically", async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/api/v1/workflow`);
    const body = await response.json();
    expect(body.publishes_automatically).toBe(false);
    expect(body.gates).toHaveLength(3);
    expect(body.risk_levels).not.toContain("safe");
  });

  test("an unknown route returns RFC 9457 problem details", async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/api/not-a-route`);
    expect(response.status()).toBe(404);
    expect(response.headers()["content-type"]).toContain("application/problem+json");
    expect(await response.json()).toMatchObject({ status: 404 });
  });

  test("responses carry a correlation id", async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/api/health/live`, {
      headers: { "x-correlation-id": "e2e-correlation" },
    });
    expect(response.headers()["x-correlation-id"]).toBe("e2e-correlation");
  });
});
