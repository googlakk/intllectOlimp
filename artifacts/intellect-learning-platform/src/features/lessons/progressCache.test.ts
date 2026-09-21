import { describe, expect, it } from 'vitest';

import { completedLessonInvalidationKeys, lessonProgressQueryKey } from './progressCache';

describe('lesson progress cache policy', () => {
  it('uses the same key shape as the lesson progress query', () => {
    expect(lessonProgressQueryKey(7, 42)).toEqual(['progress', 7, 42]);
  });

  it('refreshes learning overview data when a lesson is completed', () => {
    expect(completedLessonInvalidationKeys()).toEqual([
      ['dashboard-overview'],
      ['dashboard-students'],
      ['subjects'],
    ]);
  });
});
