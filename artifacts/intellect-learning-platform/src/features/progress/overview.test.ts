import { describe, expect, it } from 'vitest';
import type { ProgressRecord } from '@/lib/api/types';

import { buildProgressOverview } from './overview';

function progressRecord(overrides: Partial<ProgressRecord>): ProgressRecord {
  return {
    id: 1,
    student_id: 1,
    topic_id: 1,
    status: 'not_started',
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

describe('buildProgressOverview', () => {
  it('summarizes lesson, objective, and average score metrics', () => {
    const overview = buildProgressOverview([
      progressRecord({
        id: 1,
        status: 'completed',
        score: 90,
        mastery_status: 'mastered',
        objective_mastery: {
          o1: { status: 'mastered' },
          o2: { status: 'needs_practice' },
        },
      }),
      progressRecord({
        id: 2,
        status: 'in_progress',
        score: 70,
        objective_mastery: {
          o3: { status: 'mastered' },
        },
      }),
      progressRecord({
        id: 3,
        status: 'completed',
        score: null,
      }),
    ]);

    expect(overview).toEqual({
      completedLessons: 2,
      masteredLessons: 1,
      masteredObjectives: 2,
      objectivesNeedingPractice: 1,
      averageScore: 80,
      nextGoalText: 'Вернитесь к целям, которым нужна дополнительная практика.',
    });
  });

  it('keeps empty progress neutral and avoids treating null scores as zeroes', () => {
    const overview = buildProgressOverview([
      progressRecord({ score: null }),
    ]);

    expect(overview.completedLessons).toBe(0);
    expect(overview.masteredLessons).toBe(0);
    expect(overview.masteredObjectives).toBe(0);
    expect(overview.objectivesNeedingPractice).toBe(0);
    expect(overview.averageScore).toBeNull();
    expect(overview.nextGoalText).toBe(
      'Завершите урок с измеренными целями, чтобы увидеть следующий результат.',
    );
  });
});
