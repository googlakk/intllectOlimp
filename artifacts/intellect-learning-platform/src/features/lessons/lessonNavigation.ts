import type { AttemptsByStep, LessonAnswers } from './studentProgress';

export type LessonStepAdvance = {
  nextMaxOpenedStep: number;
  nextStep: number;
};

export function advanceLessonStep(currentStep: number, maxOpenedStep: number): LessonStepAdvance {
  const nextStep = currentStep + 1;
  return {
    nextMaxOpenedStep: Math.max(maxOpenedStep, nextStep),
    nextStep,
  };
}

export function applyBlockAnswer(params: {
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  blockIndex: number;
  isCorrect: boolean;
}) {
  const {
    activeOriginalIndices,
    answers,
    attemptsByStep,
    blockIndex,
    isCorrect,
  } = params;
  const originalIndex = activeOriginalIndices[blockIndex] ?? blockIndex;

  return {
    answers: { ...answers, [originalIndex]: isCorrect },
    attemptsByStep: {
      ...attemptsByStep,
      [originalIndex]: (attemptsByStep[originalIndex] || 0) + 1,
    },
    originalIndex,
  };
}

export function canNavigateToStep(index: number, maxOpenedStep: number): boolean {
  return index <= maxOpenedStep;
}
