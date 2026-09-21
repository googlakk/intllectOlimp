import { describe, expect, it } from 'vitest';
import type { ProgressRecord } from '@/lib/api/types';

import { restoreLessonProgress } from './progressRestore';

function progressRecord(overrides: Partial<ProgressRecord>): ProgressRecord {
  return {
    id: 1,
    student_id: 7,
    topic_id: 42,
    status: 'in_progress',
    score: null,
    mastery_level: null,
    time_spent_sec: 0,
    attempts: 0,
    current_step: 0,
    max_opened_step: 0,
    answers: {},
    attempts_by_step: {},
    elapsed_time_sec: 0,
    ...overrides,
  };
}

describe('restoreLessonProgress', () => {
  it('restores in-progress lesson navigation and diagnostic completion', () => {
    const restored = restoreLessonProgress(progressRecord({
      current_step: 2,
      max_opened_step: 3,
      answers: { 0: true, '1_q0': false },
      attempts_by_step: { 0: 1 },
      elapsed_time_sec: 75,
      objective_mastery: { o1: { status: 'in_progress' } },
    }), [0, 1]);

    expect(restored.currentStep).toBe(2);
    expect(restored.maxOpenedStep).toBe(3);
    expect(restored.baseElapsedTimeSec).toBe(75);
    expect(restored.diagnosticComplete).toBe(true);
    expect(restored.result).toBeNull();
  });

  it('restores completed lessons with result summary defaults', () => {
    const restored = restoreLessonProgress(progressRecord({
      status: 'completed',
      score: null,
      mastery_level: null,
      time_spent_sec: 40,
    }), []);

    expect(restored.isCompleted).toBe(true);
    expect(restored.result).toEqual({ score: 0, level: 'Начинающий' });
    expect(restored.baseElapsedTimeSec).toBe(40);
  });
});
