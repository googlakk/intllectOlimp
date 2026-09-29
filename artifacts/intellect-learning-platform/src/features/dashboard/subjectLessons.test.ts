import { describe, expect, it } from 'vitest';
import { groupLessonsBySubject, type ReportLesson } from './subjectLessons';

const lesson = (fields: Partial<ReportLesson>): ReportLesson => ({
  topic_id: 1, name: 'Тема', status: 'completed', mastery_status: 'mastered', score: 90, completed_at: null,
  subject_id: 12, subject_name: 'Математика', subject_grade: 7, archived: false, ...fields,
});

describe('groupLessonsBySubject', () => {
  it('keeps server order and counts completed and struggling lessons per subject', () => {
    const groups = groupLessonsBySubject([
      lesson({ topic_id: 1 }),
      lesson({ topic_id: 2, status: 'in_progress', mastery_status: 'needs_practice' }),
      lesson({ topic_id: 3, subject_id: 20, subject_name: 'Физика', subject_grade: 8 }),
    ]);
    expect(groups.map((group) => group.title)).toEqual(['Математика · 7 класс', 'Физика · 8 класс']);
    expect(groups[0]).toMatchObject({ completed: 1, needsHelp: 1 });
    expect(groups[0].lessons.map((item) => item.topic_id)).toEqual([1, 2]);
  });

  it('returns nothing for a student without lessons', () => {
    expect(groupLessonsBySubject([])).toEqual([]);
  });
});
