import { describe, expect, it } from "vitest";
import { buildApp } from "../src/app.js";
import { loadConfig } from "../src/config.js";
import { aggregate, checkRedis, checkSharp } from "../src/health.js";

const config = loadConfig({ APP_ENV: "local", LOG_LEVEL: "error" });

const healthyRedis = { ping: async () => "PONG" };
const brokenRedis = {
  ping: async () => {
    throw new Error("redis://user:secret@host connection refused");
  },
};

describe("component checks", () => {
  it("proves libvips can encode a PNG", async () => {
    expect((await checkSharp()).status).toBe("ok");
  });

  it("reports redis ok on PONG", async () => {
    expect((await checkRedis(healthyRedis)).status).toBe("ok");
  });

  it("reports redis down without leaking the connection string", async () => {
    const result = await checkRedis(brokenRedis);
    expect(result.status).toBe("down");
    expect(JSON.stringify(result)).not.toContain("secret");
  });
});

describe("aggregate", () => {
  it("is down when any component is down", () => {
    const report = aggregate(
      { sharp: { status: "ok" }, redis: { status: "down" } },
      "0.1.0",
      new Date(0),
    );
    expect(report.status).toBe("down");
  });

  it("is ok when everything is ok", () => {
    const report = aggregate(
      { sharp: { status: "ok" }, redis: { status: "ok" } },
      "0.1.0",
      new Date(0),
    );
    expect(report.status).toBe("ok");
    expect(report.checkedAt).toBe("1970-01-01T00:00:00.000Z");
  });
});

describe("health endpoints", () => {
  it("GET /health/live answers without touching dependencies", async () => {
    const app = buildApp({ config, redis: brokenRedis });
    const response = await app.inject({ method: "GET", url: "/health/live" });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ status: "ok" });
    await app.close();
  });

  it("GET /health returns 200 when dependencies are healthy", async () => {
    const app = buildApp({ config, redis: healthyRedis });
    const response = await app.inject({ method: "GET", url: "/health" });
    expect(response.statusCode).toBe(200);
    expect(response.json().components.redis.status).toBe("ok");
    await app.close();
  });

  it("GET /health returns 503 when Redis is unreachable", async () => {
    const app = buildApp({ config, redis: brokenRedis });
    const response = await app.inject({ method: "GET", url: "/health" });
    expect(response.statusCode).toBe(503);
    expect(response.json().status).toBe("down");
    await app.close();
  });

  it("echoes an incoming correlation id", async () => {
    const app = buildApp({ config, redis: healthyRedis });
    const response = await app.inject({
      method: "GET",
      url: "/health/live",
      headers: { "x-correlation-id": "corr-123" },
    });
    expect(response.headers["x-correlation-id"]).toBe("corr-123");
    await app.close();
  });
});
