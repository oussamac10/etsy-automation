import { describe, expect, it } from "vitest";
import {
  ApiResponseError,
  parseHealth,
} from "../composables/useApiHealth";

const valid = {
  status: "ok",
  service: "api",
  version: "0.1.0",
  app_env: "local",
  checked_at: "2026-08-01T00:00:00+00:00",
  components: {
    database: { status: "ok", detail: null, latency_ms: 3 },
    redis: { status: "ok", detail: null, latency_ms: 1 },
  },
};

describe("parseHealth", () => {
  it("accepts a well-formed report", () => {
    const health = parseHealth(valid);
    expect(health.status).toBe("ok");
    expect(Object.keys(health.components)).toEqual(["database", "redis"]);
  });

  it("accepts a degraded report", () => {
    const health = parseHealth({
      ...valid,
      status: "down",
      components: { redis: { status: "down", detail: "ConnectionError" } },
    });
    expect(health.status).toBe("down");
    expect(health.components.redis?.detail).toBe("ConnectionError");
  });

  it("rejects an unknown status value", () => {
    expect(() => parseHealth({ ...valid, status: "fine" })).toThrow(
      ApiResponseError,
    );
  });

  it("rejects a missing field", () => {
    const { version: _version, ...incomplete } = valid;
    expect(() => parseHealth(incomplete)).toThrow(ApiResponseError);
  });

  it("rejects a non-object payload", () => {
    expect(() => parseHealth("ok")).toThrow(ApiResponseError);
    expect(() => parseHealth(null)).toThrow(ApiResponseError);
  });

  it("names the offending field", () => {
    expect(() => parseHealth({ ...valid, status: "fine" })).toThrow(/status/);
  });
});
