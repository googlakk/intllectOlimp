import { describe, expect, it } from 'vitest';

import { buildSaveProgressInput } from './progressPersistence';

describe('buildSaveProgressInput', () => {
  it('builds the common in-progress persistence payload', () => {
    expect(buildSaveProgressInput({
      answers: { 1: true },
      attemptsByStep: { 1: 2 },
      elapsedTimeSec: 35,
      maxStep: 2,
      status: 'in_progress',
      step: 1,
      studentId: 7,
      topicId: 42,
    })).toEqual({
      student_id: 7,
      topic_id: 42,
      status: 'in_progress',
      current_step: 1,
      max_opened_step: 2,
      answers: { 1: true },
      attempts_by_step: { 1: 2 },
      time_spent_sec: 35,
      elapsed_time_sec: 35,
    });
  });

  it('adds completion fields only when they are supplied', () => {
    expect(buildSaveProgressInput({
      answers: { 1: true },
      attemptsByStep: { 1: 1 },
      elapsedTimeSec: 60,
      finalLevel: 'Мастер',
      finalScore: 95,
      mastery: { o1: { status: 'mastered', score: 95 } },
      masteryStatus: 'mastered',
      maxStep: 3,
      objectiveEvidence: {
        o1: [{ objective_id: 'o1', correct: true, stage: 'assessment' }],
      },
      status: 'completed',
      step: 4,
      studentId: 7,
      topicId: 42,
    })).toMatchObject({
      score: 95,
      mastery_level: 'Мастер',
      objective_mastery: { o1: { status: 'mastered', score: 95 } },
      objective_evidence: {
        o1: [{ objective_id: 'o1', correct: true, stage: 'assessment' }],
      },
      mastery_status: 'mastered',
    });
  });
});
