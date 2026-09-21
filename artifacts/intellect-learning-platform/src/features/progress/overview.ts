import type { ProgressRecord } from '@/lib/api/types';

export type ProgressOverview = {
  completedLessons: number;
  masteredLessons: number;
  masteredObjectives: number;
  objectivesNeedingPractice: number;
  averageScore: number | null;
  nextGoalText: string;
};

export function buildProgressOverview(progress: ProgressRecord[]): ProgressOverview {
  const objectiveResults = progress.flatMap((item) => Object.values(item.objective_mastery || {}));
  const objectivesNeedingPractice = objectiveResults.filter((item) => item.status === 'needs_practice').length;
  const scoreValues = progress
    .map((item) => item.score)
    .filter((score): score is number => typeof score === 'number');

  return {
    completedLessons: progress.filter((item) => item.status === 'completed').length,
    masteredLessons: progress.filter((item) => item.mastery_status === 'mastered').length,
    masteredObjectives: objectiveResults.filter((item) => item.status === 'mastered').length,
    objectivesNeedingPractice,
    averageScore: scoreValues.length
      ? Math.round(scoreValues.reduce((sum, score) => sum + score, 0) / scoreValues.length)
      : null,
    nextGoalText: objectivesNeedingPractice > 0
      ? 'Вернитесь к целям, которым нужна дополнительная практика.'
      : 'Завершите урок с измеренными целями, чтобы увидеть следующий результат.',
  };
}
