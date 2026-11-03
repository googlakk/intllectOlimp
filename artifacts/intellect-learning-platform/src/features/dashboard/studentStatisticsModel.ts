import type { StudentReportLesson } from '@/lib/api/dashboard';

export const LESSON_FILTERS = [
  { value: 'all', label: 'Все' },
  { value: 'in_progress', label: 'В процессе' },
  { value: 'completed', label: 'Пройдены' },
  { value: 'needs_practice', label: 'Нужна практика' },
] as const;
export type LessonFilter = typeof LESSON_FILTERS[number]['value'];

export function positiveId(value: string | null | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : null;
}

export function readStatisticsFilters(params: URLSearchParams) {
  const rawStatus = params.get('status');
  const status: LessonFilter = LESSON_FILTERS.some(filter => filter.value === rawStatus) ? rawStatus as LessonFilter : 'all';
  return { subjectId: positiveId(params.get('subject')), topicId: positiveId(params.get('topic')), status, search: params.get('q') ?? '' };
}

export function lessonNeedsPractice(lesson: StudentReportLesson): boolean {
  return (lesson.last_completed?.mastery_status ?? lesson.mastery_status) === 'needs_practice';
}

export function filterReportLessons(lessons: StudentReportLesson[], filters: {
  subjectId: number | null; status: LessonFilter; search: string;
}, historical = false): StudentReportLesson[] {
  const query = filters.search.trim().toLocaleLowerCase('ru-RU');
  return lessons.filter(lesson => Boolean(lesson.historical) === historical
    && (filters.subjectId === null || lesson.subject_id === filters.subjectId)
    && (!query || lesson.name.toLocaleLowerCase('ru-RU').includes(query))
    && (filters.status === 'all'
      || (filters.status === 'in_progress' && lesson.status === 'in_progress')
      || (filters.status === 'completed' && (lesson.status === 'completed' || Boolean(lesson.last_completed)))
      || (filters.status === 'needs_practice' && lessonNeedsPractice(lesson))));
}

export function lessonStateLabel(lesson: StudentReportLesson): string {
  if (lesson.retrying) return 'Повторное прохождение';
  if (lesson.status === 'completed') return 'Пройден';
  return lesson.status === 'in_progress' ? 'В процессе' : 'Не начат';
}

export function formatReportScore(value: number | null | undefined): string {
  return value == null ? 'Нет данных' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value)}%`;
}

export function formatReportDate(value: string | null | undefined): string {
  if (!value) return 'Дата не сохранена';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Дата не сохранена' : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatReportDuration(value: number | null | undefined): string {
  if (!value) return 'Не сохранено';
  if (value < 60) return `${Math.round(value)} с`;
  const minutes = Math.floor(value / 60);
  return minutes < 60 ? `${minutes} мин` : `${Math.floor(minutes / 60)} ч ${minutes % 60} мин`;
}
