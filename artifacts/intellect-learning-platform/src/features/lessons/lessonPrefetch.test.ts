import { describe, expect, it } from 'vitest';

import type { CurriculumMapTopic } from '@/lib/api/types';
import { nextPublishedLessonTopicId } from './lessonPrefetch';

const topic = (
  id: number,
  lessonStatus: CurriculumMapTopic['lesson_status'],
): CurriculumMapTopic => ({
  id,
  name: `Тема ${id}`,
  hours: 1,
  section_id: 1,
  section_name: 'Раздел',
  subject_id: 1,
  subject_name: 'Математика',
  grade: 7,
  state: 'available',
  readiness_score: 1,
  reason: 'Доступно',
  unlocked_by_topic_id: null,
  lesson_status: lessonStatus,
  mastery_status: null,
  attempts: 0,
});

describe('lesson prefetch model', () => {
  it('selects the next published lesson after the current topic', () => {
    expect(nextPublishedLessonTopicId([
      topic(1, 'published'),
      topic(2, 'preparing'),
      topic(3, 'published'),
    ], 1)).toBe(3);
  });

  it('does not wrap around or prefetch missing topics', () => {
    expect(nextPublishedLessonTopicId([topic(1, 'published')], 1)).toBeNull();
    expect(nextPublishedLessonTopicId([topic(1, 'published')], 99)).toBeNull();
  });
});
