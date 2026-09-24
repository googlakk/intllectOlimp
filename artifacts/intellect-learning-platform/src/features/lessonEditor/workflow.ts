import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import {
  useGenerateLesson,
  usePublishLesson,
  useUnpublishLesson,
  type GeneratedLesson,
  catalogInvalidationKeys,
} from '@/lib/api';

export function lessonEditorInvalidationKeys(topicId: number) {
  return [
    ...catalogInvalidationKeys,
    ['lesson', topicId] as const,
    ['lesson-manifest', topicId] as const,
    ['lesson-status', topicId] as const,
  ];
}

export function useLessonEditorWorkflow(topicId: number, lesson: GeneratedLesson | null | undefined) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const generateLessonMutation = useGenerateLesson();
  const publishLessonMutation = usePublishLesson();
  const unpublishLessonMutation = useUnpublishLesson();

  const invalidateLessonQueries = () => {
    lessonEditorInvalidationKeys(topicId).forEach((queryKey) => {
      queryClient.invalidateQueries({ queryKey });
    });
  };

  const generateLesson = () => {
    if (!user) return;
    if (lesson?.blocks.length && !window.confirm('Заменить материалы черновика? Ваши правки в черновике будут заменены после успешной генерации. Опубликованный урок останется доступен ученикам.')) return;
    generateLessonMutation.mutate(
      { topic_id: topicId, teacher_id: user.id },
      { onSuccess: invalidateLessonQueries },
    );
  };

  const togglePublication = (warningsAcknowledged: boolean) => {
    if (!lesson || !user) return;

    if (lesson.status === 'published' && !lesson.has_unpublished_changes) {
      unpublishLessonMutation.mutate(lesson.id, { onSuccess: invalidateLessonQueries });
      return;
    }

    publishLessonMutation.mutate(
      {
        lesson_id: lesson.id,
        teacher_id: user.id,
        acknowledge_warnings: warningsAcknowledged,
      },
      { onSuccess: invalidateLessonQueries },
    );
  };

  return {
    generateLesson,
    generateLessonMutation,
    publishLessonMutation,
    togglePublication,
    unpublishLessonMutation,
  };
}
