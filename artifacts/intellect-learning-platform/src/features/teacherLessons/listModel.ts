import type { Subject, Topic } from '@/lib/api/types';

export type LessonStatusView = {
  badgeClasses: string;
  badgeText: string;
};

export const LESSON_TYPE_LABELS: Record<string, string> = {
  study: 'изучение нового',
  assessment: 'контрольная работа',
  review: 'повторение',
  reflection: 'разбор ошибок',
  project: 'проект',
};

export function lessonTypeLabel(type: Topic['lesson_type']): string {
  return LESSON_TYPE_LABELS[type] ?? type;
}

export function lessonStatusView(
  lesson: Pick<Topic, 'lesson_status'> | null | undefined,
  isLoading: boolean,
): LessonStatusView | null {
  if (isLoading) return null;
  if (!lesson?.lesson_status) {
    return {
      badgeClasses: 'bg-muted text-muted-foreground',
      badgeText: 'Нет урока',
    };
  }

  if (lesson.lesson_status === 'published') {
    return {
      badgeClasses: 'bg-green-500/10 text-green-600',
      badgeText: 'Опубликован',
    };
  }

  return {
    badgeClasses: 'bg-yellow-500/10 text-yellow-600',
    badgeText: 'Черновик',
  };
}

export function parseKtpJsonText(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error('Файл должен быть валидным JSON');
  }
}

export function subjectGrades(subjects: Subject[] | undefined): number[] {
  return [...new Set((subjects ?? []).map((subject) => subject.grade))].sort((a, b) => a - b);
}

export function subjectsForGrade(subjects: Subject[] | undefined, grade: number | null): Subject[] {
  if (grade === null) return [];
  return (subjects ?? []).filter((subject) => subject.grade === grade);
}
