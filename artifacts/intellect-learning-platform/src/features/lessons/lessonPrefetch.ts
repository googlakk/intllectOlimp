import { useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import {
  getStudentLessonManifest,
  lessonManifestQueryKey,
  useCurriculumMap,
} from '@/lib/api';
import type { CurriculumMapTopic } from '@/lib/api/types';

export function nextPublishedLessonTopicId(
  topics: CurriculumMapTopic[] | undefined,
  currentTopicId: number,
): number | null {
  if (!topics?.length || !Number.isFinite(currentTopicId)) return null;
  const currentIndex = topics.findIndex((topic) => topic.id === currentTopicId);
  if (currentIndex < 0) return null;
  const nextTopic = topics
    .slice(currentIndex + 1)
    .find((topic) => topic.lesson_status === 'published');
  return nextTopic?.id ?? null;
}

export function useNextLessonManifestPrefetch({
  studentId,
  subjectId,
  topicId,
}: {
  studentId?: number;
  subjectId: number;
  topicId: number;
}) {
  const queryClient = useQueryClient();
  const curriculum = useCurriculumMap(
    studentId ?? 0,
    subjectId,
    Boolean(studentId && Number.isFinite(subjectId)),
  );
  const nextTopicId = useMemo(
    () => nextPublishedLessonTopicId(curriculum.data?.topics, topicId),
    [curriculum.data?.topics, topicId],
  );

  useEffect(() => {
    if (!studentId || !nextTopicId) return;
    const prefetchNextLesson = () => {
      void queryClient.prefetchQuery({
        queryKey: lessonManifestQueryKey(nextTopicId, studentId),
        queryFn: () => getStudentLessonManifest(nextTopicId),
        staleTime: 5 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
      });
    };
    const idleCallback = window.requestIdleCallback?.(prefetchNextLesson, { timeout: 1500 });
    const fallbackTimer = idleCallback === undefined
      ? window.setTimeout(prefetchNextLesson, 700)
      : undefined;
    return () => {
      if (idleCallback !== undefined) window.cancelIdleCallback?.(idleCallback);
      if (fallbackTimer !== undefined) window.clearTimeout(fallbackTimer);
    };
  }, [nextTopicId, queryClient, studentId]);
}
