import { defineStore } from "pinia";
import { APPROVAL_GATES, type ApprovalGate } from "@etsy/domain";

/**
 * Client-side workflow state only.
 *
 * Server state (runs, ideas, assets) is fetched deliberately by the pages that
 * need it — this store must never become a cache of API responses.
 */

export type LoadState = "idle" | "loading" | "ready" | "error";

interface WorkflowState {
  states: string[];
  gates: ApprovalGate[];
  loadState: LoadState;
  errorMessage: string | null;
}

export const useWorkflowStore = defineStore("workflow", {
  state: (): WorkflowState => ({
    states: [],
    gates: [...APPROVAL_GATES],
    loadState: "idle",
    errorMessage: null,
  }),

  getters: {
    /** The three gates are a product invariant, not a server-supplied list. */
    gateCount: (state): number => state.gates.length,
    isReady: (state): boolean => state.loadState === "ready",
  },

  actions: {
    beginLoading(): void {
      this.loadState = "loading";
      this.errorMessage = null;
    },

    setStates(states: string[]): void {
      this.states = states;
      this.loadState = "ready";
      this.errorMessage = null;
    },

    setError(message: string): void {
      this.loadState = "error";
      this.errorMessage = message;
      // Stale states must not linger behind an error banner.
      this.states = [];
    },
  },
});
