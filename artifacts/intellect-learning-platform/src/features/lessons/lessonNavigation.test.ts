import { describe, expect, it } from 'vitest';

import { advanceLessonStep, applyBlockAnswer, canNavigateToStep } from './lessonNavigation';

describe('lesson navigation model', () => {
  it('advances to the next step and expands the opened boundary', () => {
    expect(advanceLessonStep(2, 2)).toEqual({ nextStep: 3, nextMaxOpenedStep: 3 });
    expect(advanceLessonStep(2, 5)).toEqual({ nextStep: 3, nextMaxOpenedStep: 5 });
  });

  it('records answers and attempts against original block indices', () => {
    expect(applyBlockAnswer({
      activeOriginalIndices: [4, 8],
      answers: { 4: true },
      attemptsByStep: { 8: 2 },
      blockIndex: 1,
      isCorrect: false,
    })).toEqual({
      answers: { 4: true, 8: false },
      attemptsByStep: { 8: 3 },
      originalIndex: 8,
    });
  });

  it('falls back to the visible block index when no original index exists', () => {
    expect(applyBlockAnswer({
      activeOriginalIndices: [],
      answers: {},
      attemptsByStep: {},
      blockIndex: 2,
      isCorrect: true,
    })).toMatchObject({
      answers: { 2: true },
      attemptsByStep: { 2: 1 },
      originalIndex: 2,
    });
  });

  it('allows navigation only inside the opened range', () => {
    expect(canNavigateToStep(3, 3)).toBe(true);
    expect(canNavigateToStep(4, 3)).toBe(false);
  });
});
