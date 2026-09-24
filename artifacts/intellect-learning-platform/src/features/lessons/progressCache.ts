import type { QueryClient } from '@tanstack/react-query';
import type { ProgressRecord, StudentLessonManifest } from '@/lib/api/types';
export function lessonProgressQueryKey(studentId: number, topicId: number) {
  return ['progress', studentId, topicId] as const;
}

export function completedLessonInvalidationKeys() {
  return [
    ['dashboard-overview'] as const,
    ['dashboard-students'] as const,
    ['subjects'] as const,
    ['curriculum-map'] as const,
  ];
}

export function applyProgressToCache(client: QueryClient, progress: ProgressRecord) {
  client.setQueryData(lessonProgressQueryKey(progress.student_id, progress.topic_id), progress);
  client.setQueryData<StudentLessonManifest>(['lesson-manifest', progress.topic_id, progress.student_id],
    current => current ? { ...current, progress } : current);
}
