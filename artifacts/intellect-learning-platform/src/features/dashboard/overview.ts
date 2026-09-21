import type { DashboardOverview } from '@/lib/api/types';

export type DashboardMetricKey = 'students' | 'publishedLessons' | 'topics' | 'averageProgress';

export type DashboardMetric = {
  key: DashboardMetricKey;
  label: string;
  value: string;
  color: string;
  background: string;
};

export const EMPTY_DASHBOARD_OVERVIEW: DashboardOverview = {
  students: 0,
  subjects: 0,
  topics: 0,
  published_lessons: 0,
  average_progress: 0,
};

export function buildDashboardMetrics(overview: DashboardOverview = EMPTY_DASHBOARD_OVERVIEW): DashboardMetric[] {
  return [
    {
      key: 'students',
      label: 'Всего учеников',
      value: String(overview.students),
      color: 'text-blue-500',
      background: 'bg-blue-500/10',
    },
    {
      key: 'publishedLessons',
      label: 'Готовых уроков',
      value: String(overview.published_lessons),
      color: 'text-indigo-500',
      background: 'bg-indigo-500/10',
    },
    {
      key: 'topics',
      label: 'Тем в базе',
      value: String(overview.topics),
      color: 'text-purple-500',
      background: 'bg-purple-500/10',
    },
    {
      key: 'averageProgress',
      label: 'Средний прогресс',
      value: `${overview.average_progress}%`,
      color: 'text-emerald-500',
      background: 'bg-emerald-500/10',
    },
  ];
}

export function scoreBadgeClass(averageScore: number): string {
  if (averageScore >= 90) return 'bg-emerald-500/10 text-emerald-600';
  if (averageScore >= 70) return 'bg-blue-500/10 text-blue-600';
  return 'bg-amber-500/10 text-amber-600';
}
