import { describe, expect, it } from "vitest";
import { createSolidPng } from "@etsy/image-pipeline";
import { buildApp } from "../src/app.js";
import { loadConfig } from "../src/config.js";

function dummyRedis() {
  return {
    async ping() {
      return "PONG";
    },
  };
}

async function createTestImage(width = 200, height = 200) {
  const buf = await createSolidPng(width, height);
  return Buffer.from(buf).toString("base64");
}

describe("image-worker pipeline endpoints", () => {
  const config = loadConfig({
    APP_ENV: "local",
    IMAGE_WORKER_PORT: "8100",
  });
  const app = buildApp({ config, redis: dummyRedis() });

  it("POST /pipeline/analyze returns image facts", async () => {
    const base64 = await createTestImage(150, 150);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/analyze",
      payload: { image_base64: base64 },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.facts.width).toBe(150);
    expect(body.facts.height).toBe(150);
    expect(body.facts.hasAlpha).toBe(true);
  });

  it("POST /pipeline/trim-and-pad returns trimmed and padded image", async () => {
    const base64 = await createTestImage(100, 100);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/trim-and-pad",
      payload: { image_base64: base64, margin_percent: 10 },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.image_base64).toBeDefined();
    expect(body.padded_width).toBeGreaterThanOrEqual(100);
  });

  it("POST /pipeline/upscale returns 4500x5400 master canvas", async () => {
    const base64 = await createTestImage(100, 100);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/upscale",
      payload: { image_base64: base64 },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.width).toBe(4500);
    expect(body.height).toBe(5400);
    expect(body.density_dpi).toBe(300);
  });

  it("POST /pipeline/composite overlays slogan", async () => {
    const base64 = await createTestImage(500, 500);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/composite",
      payload: { image_base64: base64, slogan: "Code All Day" },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.slogan_rendered).toBe("Code All Day");
    expect(body.image_base64).toBeDefined();
  });

  it("POST /pipeline/mockup returns product mockup", async () => {
    const base64 = await createTestImage(300, 300);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/mockup",
      payload: { image_base64: base64, product_type: "tshirt" },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.product_type).toBe("tshirt");
    expect(body.image_base64).toBeDefined();
  });

  it("POST /pipeline/qa validates master PNG", async () => {
    const base64 = await createTestImage(200, 200);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/qa",
      payload: { image_base64: base64 },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.qa_report).toBeDefined();
  });

  it("POST /pipeline/process-master executes complete master pipeline", async () => {
    const base64 = await createTestImage(200, 200);
    const res = await app.inject({
      method: "POST",
      url: "/pipeline/process-master",
      payload: {
        image_base64: base64,
        exact_slogan: "Born To Code",
        intended_products: ["tshirt", "mug"],
      },
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.master_png_base64).toBeDefined();
    expect(body.typography_applied).toBe(true);
    expect(body.qa_report).toBeDefined();
    expect(body.mockups.tshirt).toBeDefined();
    expect(body.mockups.mug).toBeDefined();
  });
});
