import { describe, expect, it, vi } from "vitest";
import { HAPPY_PATH } from "@etsy/domain";
import {
  canDelete,
  isRunning,
  isStopped,
  needsOwner,
  problemDetail,
  stageLabel,
  stageProgress,
  useWorkflowControls,
} from "../composables/useWorkflowControls";

describe("when the controls are offered", () => {
  it("offers Stop only while a job is running", () => {
    expect(isRunning("RESEARCHING")).toBe(true);
    expect(isRunning("ART_GENERATION")).toBe(true);
    // Waiting at a gate is already paused; there is nothing to interrupt.
    expect(isRunning("IDEA_REVIEW")).toBe(false);
    expect(isRunning("DRAFT")).toBe(false);
    expect(isRunning("CANCELLED")).toBe(false);
  });

  it("offers Rerun only after the campaign was stopped", () => {
    expect(isStopped("CANCELLED")).toBe(true);
    expect(isStopped("RESEARCHING")).toBe(false);
    expect(isStopped("IDEA_REVIEW")).toBe(false);
  });

  it("never offers both at once", () => {
    for (const state of [...HAPPY_PATH, "CANCELLED", "PUBLISHED"]) {
      expect(isRunning(state) && isStopped(state)).toBe(false);
    }
  });
});

describe("stage reporting", () => {
  it("names every pipeline state in the owner's words", () => {
    for (const state of HAPPY_PATH) {
      expect(stageLabel(state)).not.toBe(state);
    }
    expect(stageLabel("CANCELLED")).toBe("Stopped");
  });

  it("reports position along the pipeline", () => {
    expect(stageProgress("DRAFT")).toEqual([1, HAPPY_PATH.length]);
    expect(stageProgress("ETSY_DRAFT_CREATED")).toEqual([
      HAPPY_PATH.length,
      HAPPY_PATH.length,
    ]);
    // Stopped is not a step on the path, so it claims no progress.
    expect(stageProgress("CANCELLED")[0]).toBe(0);
  });

  it("marks the gates as waiting on the owner", () => {
    expect(needsOwner("IDEA_REVIEW")).toBe(true);
    expect(needsOwner("ART_REVIEW")).toBe(true);
    expect(needsOwner("RESEARCHING")).toBe(false);
  });
});

describe("problemDetail", () => {
  it("reads an RFC 9457 detail", () => {
    expect(problemDetail({ data: { detail: "Cannot stop a finished run." } })).toBe(
      "Cannot stop a finished run.",
    );
  });

  it("returns null for anything else", () => {
    expect(problemDetail(new Error("network"))).toBeNull();
    expect(problemDetail({ data: { detail: { nested: true } } })).toBeNull();
    expect(problemDetail(null)).toBeNull();
  });
});

describe("controlWorkflow", () => {
  it("posts to the action and refreshes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", fetchMock);
    const refresh = vi.fn();

    const { controlWorkflow, controlError, pendingWorkflowId } = useWorkflowControls(
      "http://api.test/",
      refresh,
    );
    await controlWorkflow("wf-1", "cancel");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/workflows/wf-1/cancel",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(refresh).toHaveBeenCalled();
    expect(controlError.value).toBeNull();
    expect(pendingWorkflowId.value).toBeNull();
    vi.unstubAllGlobals();
  });

  it("shows the backend's reason when the state moved on", async () => {
    vi.stubGlobal(
      "$fetch",
      vi.fn().mockRejectedValue({ data: { detail: "Workflow is not running." } }),
    );

    const { controlWorkflow, controlError } = useWorkflowControls("http://api.test", vi.fn());
    await controlWorkflow("wf-1", "rerun");

    expect(controlError.value).toBe("Workflow is not running.");
    vi.unstubAllGlobals();
  });

  it("falls back to a plain message when the error carries no detail", async () => {
    vi.stubGlobal("$fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const { controlWorkflow, controlError } = useWorkflowControls("http://api.test", vi.fn());
    await controlWorkflow("wf-1", "cancel");

    expect(controlError.value).toBe("Could not stop this campaign.");
    vi.unstubAllGlobals();
  });

  it("deletes with DELETE on the campaign itself and reports success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", fetchMock);

    const { controlWorkflow } = useWorkflowControls("http://api.test", vi.fn());
    const ok = await controlWorkflow("wf-1", "delete");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/workflows/wf-1",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    );
    // The caller navigates away only when the delete actually happened.
    expect(ok).toBe(true);
    vi.unstubAllGlobals();
  });

  it("reports a refused delete instead of navigating away", async () => {
    vi.stubGlobal(
      "$fetch",
      vi.fn().mockRejectedValue({ data: { detail: "Stop the campaign before deleting it." } }),
    );

    const { controlWorkflow, controlError } = useWorkflowControls("http://api.test", vi.fn());

    expect(await controlWorkflow("wf-1", "delete")).toBe(false);
    expect(controlError.value).toBe("Stop the campaign before deleting it.");
    vi.unstubAllGlobals();
  });
});

describe("canDelete", () => {
  it("refuses only while a job still holds the campaign", () => {
    expect(canDelete("RESEARCHING")).toBe(false);
    expect(canDelete("ART_QUEUED")).toBe(false);
    // Everything paused or finished can be cleared off the list.
    expect(canDelete("DRAFT")).toBe(true);
    expect(canDelete("IDEA_REVIEW")).toBe(true);
    expect(canDelete("CANCELLED")).toBe(true);
    expect(canDelete("ETSY_DRAFT_CREATED")).toBe(true);
  });
});
