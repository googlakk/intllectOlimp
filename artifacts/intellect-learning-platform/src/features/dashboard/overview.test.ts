import { describe, expect, it } from 'vitest';

import { buildDashboardMetrics, scoreBadgeClass } from './overview';

describe('buildDashboardMetrics', () => {
  it('maps dashboard overview into stable metric view models', () => {
    expect(buildDashboardMetrics({
      students: 142,
      subjects: 5,
      topics: 84,
      published_lessons: 32,
      average_progress: 48,
    })).toMatchObject([
      { key: 'students', label: 'Всего учеников', value: '142' },
      { key: 'publishedLessons', label: 'Готовых уроков', value: '32' },
      { key: 'topics', label: 'Тем в базе', value: '84' },
      { key: 'averageProgress', label: 'Средний прогресс', value: '48%' },
    ]);
  });

  it('uses neutral empty metrics while server data is not available', () => {
    expect(buildDashboardMetrics().map((metric) => metric.value)).toEqual(['0', '0', '0', '0%']);
  });
});

describe('scoreBadgeClass', () => {
  it('classifies high, medium, and low student scores', () => {
    expect(scoreBadgeClass(95)).toBe('bg-emerald-500/10 text-emerald-600');
    expect(scoreBadgeClass(70)).toBe('bg-blue-500/10 text-blue-600');
    expect(scoreBadgeClass(69)).toBe('bg-amber-500/10 text-amber-600');
  });
});
