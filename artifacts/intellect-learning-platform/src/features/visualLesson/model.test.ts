import { describe, expect, it } from 'vitest';
import { answerFeedback, initialState, recordAnswer, restoreState } from './model';

describe('garden lesson progress', () => {
  it('retains attempts when correcting a misconception', () => {
    const wrong = recordAnswer(initialState(), 'trap', 8);
    expect(wrong.responses.trap).toEqual({ value: 8, correct: false, tries: 1 });
    const correct = recordAnswer(wrong, 'trap', 4);
    expect(correct.responses.trap).toEqual({ value: 4, correct: true, tries: 2 });
    expect(recordAnswer(correct, 'trap', 4)).toBe(correct);
  });
  it('does not count negative roots or nonfinite input as correct', () => {
    expect(recordAnswer(initialState(), 'trap', -4).responses.trap?.correct).toBe(false);
    expect(recordAnswer(initialState(), 'project', NaN)).toEqual(initialState());
    expect(answerFeedback('project', { value: -7, tries: 1, correct: false })).toContain('длина стороны не может быть отрицательной');
  });
  it('restores exact valid progress after reload', () => {
    const state = { ...recordAnswer(initialState(), 'project', 7), step: 7, side: 8 };
    expect(restoreState(JSON.stringify(state))).toEqual(state);
  });
  it('recovers malformed and unsupported storage safely', () => {
    for (const raw of [null, '{broken', 'null', '[]', '{"version":2}']) expect(restoreState(raw)).toEqual(initialState());
    expect(restoreState(JSON.stringify({ version: 1, step: 999, side: -1, responses: { project: { value: '7', tries: 1 } } }))).toEqual(initialState());
  });
  it('derives correctness from answers instead of persisted flags', () => {
    const restored = restoreState(JSON.stringify({ version: 1, responses: { trap: { value: 8, tries: 2, correct: true } } }));
    expect(restored.responses.trap?.correct).toBe(false);
  });
});
