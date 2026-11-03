import { describe, expect, it } from 'vitest';
import type { StudentReportLesson } from '@/lib/api/dashboard';
import { filterReportLessons, formatReportDate, formatReportDuration, formatReportScore, lessonStateLabel, positiveId, readStatisticsFilters } from './studentStatisticsModel';

const lesson = (changes: Partial<StudentReportLesson> = {}): StudentReportLesson => ({
  topic_id: 1, name: 'Закон Ома', status: 'not_started', mastery_status: 'not_assessed', score: null,
  completed_at: null, subject_id: 5, subject_name: 'Физика', subject_grade: 8,
  archived: false, published: true, historical: false, retrying: false, has_progress: false,
  started_at: null, updated_at: null, elapsed_time_sec: 0, last_completed: null, ...changes,
});

describe('student statistics filters', () => {
  it('restores subject, task, status and search from a shareable URL', () => {
    expect(readStatisticsFilters(new URLSearchParams('subject=5&topic=7&status=needs_practice&q=Закон'))).toEqual({ subjectId: 5, topicId: 7, status: 'needs_practice', search: 'Закон' });
  });

  it('ignores malformed identifiers and unsupported statuses', () => {
    expect(readStatisticsFilters(new URLSearchParams('subject=-1&topic=NaN&status=wrong'))).toEqual({ subjectId: null, topicId: null, status: 'all', search: '' });
    expect(positiveId('9007199254740992')).toBeNull();
    expect(positiveId('2.5')).toBeNull();
    expect(positiveId('0')).toBeNull();
  });

  it('keeps same-name subjects separate and searches without case sensitivity', () => {
    const data = [lesson(), lesson({ topic_id: 2, subject_id: 8 }), lesson({ topic_id: 3, name: 'Плотность' })];
    expect(filterReportLessons(data, { subjectId: 5, status: 'all', search: '  ЗАКОН ' }).map(item => item.topic_id)).toEqual([1]);
  });

  it('keeps archived and other-grade results out of current lessons', () => {
    const data = [lesson(), lesson({ topic_id: 2, historical: true, archived: true }), lesson({ topic_id: 3, subject_grade: 7, historical: true })];
    const filters = { subjectId: null, status: 'all' as const, search: '' };
    expect(filterReportLessons(data, filters).map(item => item.topic_id)).toEqual([1]);
    expect(filterReportLessons(data, filters, true).map(item => item.topic_id)).toEqual([2, 3]);
  });

  it('shows retrying lesson as both in-progress and previously completed without losing last mastery', () => {
    const retry = lesson({ retrying: true, status: 'in_progress', has_progress: true, last_completed: { score: 0, mastery_status: 'needs_practice', completed_at: '2026-10-01T10:00:00Z', elapsed_time_sec: 100, lesson_version_id: 10 } });
    for (const status of ['in_progress', 'completed', 'needs_practice'] as const) {
      expect(filterReportLessons([retry], { subjectId: null, status, search: '' })).toEqual([retry]);
    }
    expect(lessonStateLabel(retry)).toBe('Повторное прохождение');
  });

  it('uses saved mastery rather than a numeric score threshold', () => {
    const data = [lesson({ topic_id: 1, score: 20, mastery_status: 'mastered' }), lesson({ topic_id: 2, score: 95, mastery_status: 'needs_practice' })];
    expect(filterReportLessons(data, { subjectId: null, status: 'needs_practice', search: '' }).map(item => item.topic_id)).toEqual([2]);
  });
});

describe('report labels', () => {
  it('distinguishes a genuine zero score from no measurement', () => {
    expect(formatReportScore(0)).toBe('0%');
    expect(formatReportScore(null)).toBe('Нет данных');
    expect(formatReportScore(undefined)).toBe('Нет данных');
    expect(formatReportScore(86.25)).toBe('86,3%');
  });

  it('handles unavailable dates and short or long saved durations', () => {
    expect(formatReportDate('invalid')).toBe('Дата не сохранена');
    expect(formatReportDate(null)).toBe('Дата не сохранена');
    expect(formatReportDuration(0)).toBe('Не сохранено');
    expect(formatReportDuration(42)).toBe('42 с');
    expect(formatReportDuration(125)).toBe('2 мин');
    expect(formatReportDuration(3660)).toBe('1 ч 1 мин');
  });
});
