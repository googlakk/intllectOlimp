import type { GeneratedLesson, LearningObjective } from '@/lib/api/types';

export function lessonObjectives(lesson: GeneratedLesson | null | undefined): LearningObjective[] {
  const configured = lesson?.lesson_metadata?.objectives;
  return Array.isArray(configured) ? configured : [];
}

export function lessonHeaderText(lesson: GeneratedLesson | null | undefined) {
  return {
    learningObjective: String(lesson?.lesson_metadata?.learning_objectives || ''),
    topicTitle: String(lesson?.lesson_metadata?.topic_name || 'Урок'),
  };
}
