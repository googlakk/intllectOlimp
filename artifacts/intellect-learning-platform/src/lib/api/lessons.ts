import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { readPersistentRequestCache, request, requestCached, requestNullable } from './client';
import type { Block, GeneratedLesson, StudentLessonManifest } from './types';

const LESSON_READ_CACHE_MS = 5 * 60 * 1000;

export const lessonQueryKey = (
  topicId: number,
  role?: 'student' | 'teacher',
  studentId?: number,
) => ['lesson', topicId, role, studentId] as const;

export const lessonManifestQueryKey = (topicId: number, studentId?: number) =>
  ['lesson-manifest', topicId, studentId] as const;

export async function getLessonByTopic(
  topicId: number,
  role?: 'student' | 'teacher',
  studentId?: number,
): Promise<GeneratedLesson | null> {
  const params = new URLSearchParams();
  if (role) params.set('role', role);
  if (studentId) params.set('student_id', String(studentId));
  const query = params.size ? `?${params.toString()}` : '';
  return requestNullable<GeneratedLesson>(`/lessons/${topicId}${query}`);
}

const lessonManifestPath = (topicId: number) => `/lessons/${topicId}/manifest`;

export const getStudentLessonManifest = (topicId: number) =>
  requestCached<StudentLessonManifest>(lessonManifestPath(topicId), LESSON_READ_CACHE_MS);

export const generateLesson = (topicId: number, teacherId: number, model?: string) =>
  request<GeneratedLesson>('/lessons/generate', {
    method: 'POST',
    body: JSON.stringify({ topic_id: topicId, teacher_id: teacherId, ...(model ? { model } : {}) }),
  });

export const updateLessonBlocks = (lessonId: number, blocks: Block[]) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/blocks`, {
    method: 'PUT',
    body: JSON.stringify({ blocks }),
  });

export const publishLesson = (lessonId: number, teacherId: number, acknowledgeWarnings = false, overrideErrors = false) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/publish`, {
    method: 'PUT',
    body: JSON.stringify({ teacher_id: teacherId, acknowledge_warnings: acknowledgeWarnings, override_errors: overrideErrors }),
  });

export const unpublishLesson = (lessonId: number) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/unpublish`, { method: 'PUT' });

export const useGetLesson = (
  topicId: number,
  role?: 'student' | 'teacher',
  enabled = true,
  studentId?: number,
) =>
  useQuery({
    queryKey: lessonQueryKey(topicId, role, studentId),
    queryFn: () => getLessonByTopic(topicId, role, studentId),
    enabled: enabled && topicId > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

export const useStudentLessonManifest = (
  topicId: number,
  studentId?: number,
  enabled = true,
) => {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: lessonManifestQueryKey(topicId, studentId),
    queryFn: () => getStudentLessonManifest(topicId),
    enabled: enabled && topicId > 0 && Boolean(studentId),
    initialData: () => readPersistentRequestCache<StudentLessonManifest>(lessonManifestPath(topicId))?.data,
    initialDataUpdatedAt: () => readPersistentRequestCache<StudentLessonManifest>(lessonManifestPath(topicId))?.updatedAt,
    staleTime: LESSON_READ_CACHE_MS,
    gcTime: 30 * 60 * 1000,
  });
  useEffect(() => {
    if (!query.data) return;
    queryClient.setQueryData(lessonQueryKey(topicId, 'student', studentId), query.data.lesson);
    queryClient.setQueryData(['progress', studentId, topicId], query.data.progress);
  }, [query.data, queryClient, studentId, topicId]);
  return query;
};

export const useGenerateLesson = () =>
  useMutation({
    mutationFn: (data: { topic_id: number; teacher_id: number; model?: string }) =>
      generateLesson(data.topic_id, data.teacher_id, data.model),
  });

export const useUpdateLessonBlocks = () =>
  useMutation({
    mutationFn: (data: { lesson_id: number; blocks: Block[] }) =>
      updateLessonBlocks(data.lesson_id, data.blocks),
  });

export const usePublishLesson = () =>
  useMutation({
    mutationFn: (data: { lesson_id: number; teacher_id: number; acknowledge_warnings?: boolean; override_errors?: boolean }) =>
      publishLesson(data.lesson_id, data.teacher_id, data.acknowledge_warnings, data.override_errors),
  });

export const useUnpublishLesson = () =>
  useMutation({
    mutationFn: (lessonId: number) => unpublishLesson(lessonId),
  });

export const useCreateLessonDraft = () => useMutation({
  mutationFn: (data: { topic_id: number; teacher_id: number }) => request<GeneratedLesson>('/lessons/draft', { method: 'POST', body: JSON.stringify(data) }),
});
