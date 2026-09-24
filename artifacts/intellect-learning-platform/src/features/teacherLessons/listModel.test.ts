import { describe, expect, it } from 'vitest';
import { lessonStatusView, lessonTypeLabel, parseKtpJsonText, subjectGrades, subjectsForGrade } from './listModel';
import type { Subject } from '@/lib/api/types';

describe('teacher lesson list model', () => {
  it('formats known and unknown lesson types', () => {
    expect(lessonTypeLabel('study')).toBe('изучение нового');
    expect(lessonTypeLabel('assessment')).toBe('контрольная работа');
    expect(lessonTypeLabel('review')).toBe('повторение');
    expect(lessonTypeLabel('reflection')).toBe('разбор ошибок');
    expect(lessonTypeLabel('seminar')).toBe('seminar');
  });

  it('hides status badge while lesson status is loading', () => {
    expect(lessonStatusView(undefined, true)).toBeNull();
  });

  it('maps missing, draft and published lesson status to badge view data', () => {
    expect(lessonStatusView(null, false)).toEqual({
      badgeClasses: 'bg-muted text-muted-foreground',
      badgeText: 'Нет урока',
    });
    expect(lessonStatusView({ lesson_status: 'draft' }, false)).toEqual({
      badgeClasses: 'bg-yellow-500/10 text-yellow-600',
      badgeText: 'Черновик',
    });
    expect(lessonStatusView({ lesson_status: 'published' }, false)).toEqual({
      badgeClasses: 'bg-green-500/10 text-green-600',
      badgeText: 'Опубликован',
    });
  });

  it('parses KTP JSON text and reports invalid JSON in user-facing wording', () => {
    expect(parseKtpJsonText('{"subject":"math"}')).toEqual({ subject: 'math' });
    expect(() => parseKtpJsonText('{bad json')).toThrow('Файл должен быть валидным JSON');
  });

  it('groups subjects by grade without mixing curricula', () => {
    const subjects = [
      { id: 1, name: 'Математика', grade: 8 },
      { id: 2, name: 'Физика', grade: 7 },
      { id: 3, name: 'Математика', grade: 7 },
    ] as Subject[];

    expect(subjectGrades(subjects)).toEqual([7, 8]);
    expect(subjectsForGrade(subjects, 7).map((subject) => subject.id)).toEqual([2, 3]);
    expect(subjectsForGrade(subjects, null)).toEqual([]);
  });
});
