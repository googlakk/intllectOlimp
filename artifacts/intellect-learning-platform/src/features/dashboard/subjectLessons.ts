import type { StudentLearningReport } from '@/lib/api/dashboard';

export type ReportLesson = StudentLearningReport['lessons'][number];

export type SubjectLessons = {
  subjectId: number;
  title: string;
  lessons: ReportLesson[];
  completed: number;
  needsHelp: number;
};

/** Уроки ученика по предметам — в том порядке, в каком их отдал сервер (предмет, класс, программа). */
export function groupLessonsBySubject(lessons: ReportLesson[]): SubjectLessons[] {
  const groups = new Map<number, SubjectLessons>();
  for (const lesson of lessons) {
    let group = groups.get(lesson.subject_id);
    if (!group) {
      group = { subjectId: lesson.subject_id, title: `${lesson.subject_name} · ${lesson.subject_grade} класс`, lessons: [], completed: 0, needsHelp: 0 };
      groups.set(lesson.subject_id, group);
    }
    group.lessons.push(lesson);
    if (lesson.status === 'completed') group.completed += 1;
    if (lesson.mastery_status === 'needs_practice') group.needsHelp += 1;
  }
  return [...groups.values()];
}
