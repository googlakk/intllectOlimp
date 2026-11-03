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

it('keeps the latest submitted answer through subsequent answer and completion saves', () => {
  const responses = { current: {} as import('./responseDetails').ResponseDetails };
  const build = (status: 'in_progress' | 'completed') => buildSaveProgressInput({
    studentId: 1, topicId: 2, status, answers: { '3_q0': true }, attemptsByStep: {},
    elapsedTimeSec: 12, maxStep: 3, step: 3, responseDetails: responses.current,
  });
  responses.current = { '3_q0': { value: '42', outcome: 'correct', questionIndex: 0 } };
  const intermediate = build('in_progress');
  const completed = build('completed');
  expect(intermediate.response_details).toEqual(responses.current);
  expect(completed.response_details?.['3_q0'].value).toBe('42');
});
