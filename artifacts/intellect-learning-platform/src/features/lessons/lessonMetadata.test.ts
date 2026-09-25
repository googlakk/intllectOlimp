import { describe, expect, it } from 'vitest';
import type { GeneratedLesson } from '@/lib/api/types';

import { lessonHeaderText, lessonObjectives, lessonPlanningSummary } from './lessonMetadata';

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
      textbookRef: null,
    });
    expect(lessonHeaderText(null)).toEqual({ learningObjective: '', topicTitle: 'Урок', textbookRef: null });
  });

  it('returns configured objectives only when metadata contains an array', () => {
    expect(lessonObjectives(lesson)).toEqual([{ id: 'o1', text: 'Solve' }]);
    expect(lessonObjectives({ lesson_metadata: { objectives: 'bad' } } as unknown as GeneratedLesson)).toEqual([]);
  });

  it('formats lesson planning metadata for teacher UI', () => {
    const planned = {
      lesson_metadata: {
        topic_contract: {
          volume: 'extended',
          complexity: 'high',
          objective_count: 3,
          lesson_shape: 'process_inquiry',
          media_policy: 'suggested',
          block_budget: { min: 12, max: 18, heavy_max: 3 },
        },
      },
    } as GeneratedLesson;

    expect(lessonPlanningSummary(planned)).toMatchObject({
      volumeLabel: 'расширенная тема',
      shapeLabel: 'исследование процесса',
      objectiveCount: 3,
      mediaPolicy: 'suggested',
      blockRange: '12-18',
    });
    expect(lessonPlanningSummary(null)).toBeNull();
  });
});
