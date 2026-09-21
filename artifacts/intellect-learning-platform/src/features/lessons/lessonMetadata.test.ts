import { describe, expect, it } from 'vitest';
import type { GeneratedLesson } from '@/lib/api/types';

import { lessonHeaderText, lessonObjectives } from './lessonMetadata';

const lesson = {
  lesson_metadata: {
    learning_objectives: 'Solve equations',
    objectives: [{ id: 'o1', text: 'Solve' }],
    topic_name: 'Linear equations',
  },
} as GeneratedLesson;

describe('lesson metadata helpers', () => {
  it('extracts stable header text with defaults', () => {
    expect(lessonHeaderText(lesson)).toEqual({
      learningObjective: 'Solve equations',
      topicTitle: 'Linear equations',
    });
    expect(lessonHeaderText(null)).toEqual({ learningObjective: '', topicTitle: 'Урок' });
  });

  it('returns configured objectives only when metadata contains an array', () => {
    expect(lessonObjectives(lesson)).toEqual([{ id: 'o1', text: 'Solve' }]);
    expect(lessonObjectives({ lesson_metadata: { objectives: 'bad' } } as unknown as GeneratedLesson)).toEqual([]);
  });
});
