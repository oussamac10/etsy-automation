import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import { HAPPY_PATH } from '@etsy/domain';
import { FALLBACK_STATES, parseWorkflow } from '../composables/useWorkflow';
import {
  canDelete,
  isRunning,
  isStopped,
  needsOwner,
  problemDetail,
  stageLabel,
  stageProgress,
} from '../composables/useWorkflowControls';
import { useWorkflowStore } from '../stores/workflow';

const validWorkflow = {
  states: ['RESEARCHING', 'IDEA_REVIEW'],
  failure_states: ['RESEARCH_FAILED'],
  gates: [
    {
      gate: 'IDEA_APPROVAL',
      decided_from: 'IDEA_REVIEW',
      advances_to: 'ART_GENERATION',
    },
  ],
  risk_levels: ['low', 'medium', 'high', 'unknown'],
  publishes_automatically: false,
};

describe('Workflow Pipeline & Parse Workflow Composable', () => {
  it('accepts a well-formed description', () => {
    expect(parseWorkflow(validWorkflow).states).toEqual(['RESEARCHING', 'IDEA_REVIEW']);
  });

  it('refuses a payload that claims automatic publishing', () => {
    expect(() =>
      parseWorkflow({ ...validWorkflow, publishes_automatically: true })
    ).toThrow(/automatic publishing/);
  });

  it('rejects an empty state list', () => {
    expect(() => parseWorkflow({ ...validWorkflow, states: [] })).toThrow();
  });

  it('rejects a malformed gate', () => {
    expect(() =>
      parseWorkflow({ ...validWorkflow, gates: [{ gate: 'IDEA_APPROVAL' }] })
    ).toThrow();
  });

  it('FALLBACK_STATES matches the shared domain pipeline', () => {
    expect(FALLBACK_STATES[0]).toBe('DRAFT');
    expect(FALLBACK_STATES).toContain('ETSY_DRAFT_CREATED');
    expect(FALLBACK_STATES).toHaveLength(16);
  });
});

describe('Workflow Controls Composable', () => {
  describe('Control Availability', () => {
    it('offers Stop only while a job is running', () => {
      expect(isRunning('RESEARCHING')).toBe(true);
      expect(isRunning('ART_GENERATION')).toBe(true);
      // Waiting at a gate is already paused; there is nothing to interrupt.
      expect(isRunning('IDEA_REVIEW')).toBe(false);
      expect(isRunning('DRAFT')).toBe(false);
      expect(isRunning('CANCELLED')).toBe(false);
    });

    it('offers Rerun only after the campaign was stopped', () => {
      expect(isStopped('CANCELLED')).toBe(true);
      expect(isStopped('RESEARCHING')).toBe(false);
      expect(isStopped('IDEA_REVIEW')).toBe(false);
    });

    it('never offers both at once', () => {
      for (const state of [...HAPPY_PATH, 'CANCELLED', 'PUBLISHED']) {
        expect(isRunning(state) && isStopped(state)).toBe(false);
      }
    });
  });

  describe('Stage Reporting', () => {
    it("names every pipeline state in the owner's words", () => {
      for (const state of HAPPY_PATH) {
        expect(stageLabel(state)).not.toBe(state);
      }
      expect(stageLabel('CANCELLED')).toBe('Stopped');
    });

    it('reports position along the pipeline', () => {
      expect(stageProgress('DRAFT')).toEqual([1, HAPPY_PATH.length]);
      expect(stageProgress('ETSY_DRAFT_CREATED')).toEqual([
        HAPPY_PATH.length,
        HAPPY_PATH.length,
      ]);
      // Stopped is not a step on the path, so it claims no progress.
      expect(stageProgress('CANCELLED')[0]).toBe(0);
    });

    it('marks the gates as waiting on the owner', () => {
      expect(needsOwner('IDEA_REVIEW')).toBe(true);
      expect(needsOwner('ART_REVIEW')).toBe(true);
      expect(needsOwner('RESEARCHING')).toBe(false);
    });
  });

  describe('Problem Detail Mapping & Deletion', () => {
    it('extracts detail from problem payload or returns null', () => {
      expect(problemDetail({ data: { detail: 'Specific error' } })).toBe('Specific error');
      expect(problemDetail({ data: { detail: 'requires gate IDEA_APPROVAL' } })).toBe(
        'Please approve the concept before proceeding.'
      );
      expect(problemDetail({})).toBeNull();
      expect(problemDetail(null)).toBeNull();
    });

    it('determines delete eligibility', () => {
      expect(canDelete('DRAFT')).toBe(true);
      expect(canDelete('CANCELLED')).toBe(true);
      expect(canDelete('RESEARCHING')).toBe(false);
    });
  });
});

describe('Workflow Pinia Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('starts idle with the three gates', () => {
    const store = useWorkflowStore();
    expect(store.loadState).toBe('idle');
    expect(store.gateCount).toBe(3);
    expect(store.states).toEqual([]);
  });

  it('moves through loading to ready', () => {
    const store = useWorkflowStore();
    store.beginLoading();
    expect(store.loadState).toBe('loading');
    store.setStates(['RESEARCHING']);
    expect(store.isReady).toBe(true);
    expect(store.states).toEqual(['RESEARCHING']);
  });

  it('clears stale states on error', () => {
    const store = useWorkflowStore();
    store.setStates(['RESEARCHING']);
    store.setError('API unreachable');
    expect(store.loadState).toBe('error');
    expect(store.states).toEqual([]);
    expect(store.errorMessage).toBe('API unreachable');
  });

  it('clears a previous error when loading again', () => {
    const store = useWorkflowStore();
    store.setError('boom');
    store.beginLoading();
    expect(store.errorMessage).toBeNull();
  });
});
