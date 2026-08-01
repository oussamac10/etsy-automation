import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useWorkflowStore } from "../stores/workflow";

describe("workflow store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("starts idle with the three gates", () => {
    const store = useWorkflowStore();
    expect(store.loadState).toBe("idle");
    expect(store.gateCount).toBe(3);
    expect(store.states).toEqual([]);
  });

  it("moves through loading to ready", () => {
    const store = useWorkflowStore();
    store.beginLoading();
    expect(store.loadState).toBe("loading");
    store.setStates(["RESEARCHING"]);
    expect(store.isReady).toBe(true);
    expect(store.states).toEqual(["RESEARCHING"]);
  });

  it("clears stale states on error", () => {
    const store = useWorkflowStore();
    store.setStates(["RESEARCHING"]);
    store.setError("API unreachable");
    expect(store.loadState).toBe("error");
    expect(store.states).toEqual([]);
    expect(store.errorMessage).toBe("API unreachable");
  });

  it("clears a previous error when loading again", () => {
    const store = useWorkflowStore();
    store.setError("boom");
    store.beginLoading();
    expect(store.errorMessage).toBeNull();
  });
});
