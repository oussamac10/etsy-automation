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
  test("renders live service status from the API", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "Etsy PNG Automation", level: 1 }),
    ).toBeVisible();

    const statusList = page.getByTestId("status-list");
    await expect(statusList).toBeVisible();

    // Each dependency the API reports must appear by name.
    for (const name of ["api", "database", "redis", "image_worker"]) {
      await expect(statusList.getByText(name, { exact: true })).toBeVisible();
    }
  });

  test("shows the workflow states in order", async ({ page }) => {
    await page.goto("/");
    const items = page.getByTestId("workflow-states").getByRole("listitem");
    // Phase 2 extended the pipeline to sixteen states: fourteen on the happy
    // path plus PUBLISHED and CANCELLED, which leave it.
    await expect(items).toHaveCount(16);
    await expect(items.first()).toContainText("DRAFT");
    await expect(items.nth(13)).toContainText("ETSY_DRAFT_CREATED");
    await expect(items.last()).toContainText("CANCELLED");
  });

  test("states the three human gates", async ({ page }) => {
    await page.goto("/");
    const gates = page.getByTestId("gate-list").getByRole("listitem");
    await expect(gates).toHaveCount(3);
    await expect(gates.nth(0)).toContainText("Idea approval");
    await expect(gates.nth(1)).toContainText("Artwork approval");
    await expect(gates.nth(2)).toContainText("Trademark");
  });

  test("never shows a safety or profit badge", async ({ page }) => {
    await page.goto("/");

    // Status chips and workflow labels are where a reassuring badge would
    // appear. The prose is checked separately, because the disclaimer legitimately
    // uses these words in a negation.
    const labels = [
      await page.getByTestId("status-list").innerText(),
      await page.getByTestId("workflow-states").innerText(),
      await page.getByTestId("gate-list").innerText(),
    ]
      .join(" ")
      .toLowerCase();

    for (const forbidden of [
      "safe",
      "trademark-free",
      "guaranteed",
      "profitable",
      "risk-free",
    ]) {
      expect(labels).not.toContain(forbidden);
    }
  });

  test("states the disclaimer rather than a promise", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText(/never publishes or activates a listing/i),
    ).toBeVisible();
    await expect(
      page.getByText(/makes no claim that an idea is profitable/i),
    ).toBeVisible();
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
