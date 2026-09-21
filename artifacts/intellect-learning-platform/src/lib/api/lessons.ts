import { useMutation, useQuery } from '@tanstack/react-query';

import { request, requestNullable } from './client';
import type { Block, GeneratedLesson } from './types';

export async function getLessonByTopic(
  topicId: number,
  role?: 'student' | 'teacher',
): Promise<GeneratedLesson | null> {
  return requestNullable<GeneratedLesson>(`/lessons/${topicId}${role ? `?role=${role}` : ''}`);
}

export const generateLesson = (topicId: number, teacherId: number) =>
  request<GeneratedLesson>('/lessons/generate', {
    method: 'POST',
    body: JSON.stringify({ topic_id: topicId, teacher_id: teacherId }),
  });

export const updateLessonBlocks = (lessonId: number, blocks: Block[]) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/blocks`, {
    method: 'PUT',
    body: JSON.stringify({ blocks }),
  });

export const publishLesson = (lessonId: number, teacherId: number, acknowledgeWarnings = false) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/publish`, {
    method: 'PUT',
    body: JSON.stringify({ teacher_id: teacherId, acknowledge_warnings: acknowledgeWarnings }),
  });

export const unpublishLesson = (lessonId: number) =>
  request<GeneratedLesson>(`/lessons/${lessonId}/unpublish`, { method: 'PUT' });

export const useGetLesson = (topicId: number, role?: 'student' | 'teacher', enabled = true) =>
  useQuery({
    queryKey: ['lesson', topicId, role],
    queryFn: () => getLessonByTopic(topicId, role),
    enabled: enabled && topicId > 0,
  });

export const useGenerateLesson = () =>
  useMutation({
    mutationFn: (data: { topic_id: number; teacher_id: number }) =>
      generateLesson(data.topic_id, data.teacher_id),
  });

export const useUpdateLessonBlocks = () =>
  useMutation({
    mutationFn: (data: { lesson_id: number; blocks: Block[] }) =>
      updateLessonBlocks(data.lesson_id, data.blocks),
  });

export const usePublishLesson = () =>
  useMutation({
    mutationFn: (data: { lesson_id: number; teacher_id: number; acknowledge_warnings?: boolean }) =>
      publishLesson(data.lesson_id, data.teacher_id, data.acknowledge_warnings),
  });

export const useUnpublishLesson = () =>
  useMutation({
    mutationFn: (lessonId: number) => unpublishLesson(lessonId),
  });

export const useLessonStatus = (topicId: number, enabled = true) =>
  useQuery({
    queryKey: ['lesson-status', topicId],
    queryFn: () => getLessonByTopic(topicId, 'teacher'),
    enabled: enabled && topicId > 0,
  });
