import { describe, expect, it } from "vitest";
import { ConfigError, loadConfig, pinoLevel } from "../src/config.js";

describe("loadConfig", () => {
  it("applies defaults for an empty environment", () => {
    const config = loadConfig({});
    expect(config.APP_ENV).toBe("local");
    expect(config.IMAGE_WORKER_PORT).toBe(8100);
    expect(config.LOG_LEVEL).toBe("info");
  });

  it("accepts the upper-case log levels used in .env.example", () => {
    expect(loadConfig({ LOG_LEVEL: "INFO" }).LOG_LEVEL).toBe("info");
    expect(loadConfig({ LOG_LEVEL: "WARNING" }).LOG_LEVEL).toBe("warning");
  });

  it("treats an empty string as absent so blank .env lines use defaults", () => {
    expect(loadConfig({ IMAGE_WORKER_PORT: "" }).IMAGE_WORKER_PORT).toBe(8100);
  });

  it("coerces numeric settings", () => {
    expect(loadConfig({ IMAGE_WORKER_PORT: "9001" }).IMAGE_WORKER_PORT).toBe(
      9001,
    );
  });

  it("rejects an out-of-range port", () => {
    expect(() => loadConfig({ IMAGE_WORKER_PORT: "70000" })).toThrow(
      ConfigError,
    );
  });

  it("rejects an unknown APP_ENV", () => {
    expect(() => loadConfig({ APP_ENV: "prod" })).toThrow(ConfigError);
  });

  it("names the offending variable in the error", () => {
    expect(() => loadConfig({ APP_ENV: "prod" })).toThrow(/APP_ENV/);
  });
});

describe("pinoLevel", () => {
  it("maps warning onto warn", () => {
    expect(pinoLevel("warning")).toBe("warn");
    expect(pinoLevel("info")).toBe("info");
  });
});
