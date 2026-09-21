import type { ObjectiveEvidence, ObjectiveMastery, ProgressRecord } from '@/lib/api/types';
import { isDiagnosticFinished, type AttemptsByStep, type LessonAnswers } from './studentProgress';

export type RestoredLessonProgress = {
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  baseElapsedTimeSec: number;
  currentStep: number;
  diagnosticComplete: boolean;
  isCompleted: boolean;
  maxOpenedStep: number;
  objectiveEvidence: Record<string, ObjectiveEvidence[]>;
  objectiveMastery: Record<string, ObjectiveMastery>;
  result: { score: number; level: string } | null;
};

export function restoreLessonProgress(
  progress: ProgressRecord,
  diagnosticOriginalIndices: number[],
): RestoredLessonProgress {
  const isCompleted = progress.status === 'completed';
  const answers = progress.answers || {};
  const objectiveMastery = progress.objective_mastery || {};

  return {
    answers,
    attemptsByStep: progress.attempts_by_step || {},
    baseElapsedTimeSec: progress.elapsed_time_sec || progress.time_spent_sec || 0,
    currentStep: isCompleted ? 0 : progress.current_step || 0,
    diagnosticComplete: Boolean(progress.objective_mastery)
      && isDiagnosticFinished(diagnosticOriginalIndices, answers),
    isCompleted,
    maxOpenedStep: progress.max_opened_step || 0,
    objectiveEvidence: progress.objective_evidence || {},
    objectiveMastery,
    result: isCompleted
      ? { score: progress.score || 0, level: progress.mastery_level || 'Начинающий' }
      : null,
  };
}
