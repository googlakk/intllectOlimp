import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { request, requestNullable } from './client';
import type {
  MasteryStatus,
  ObjectiveEvidence,
  ObjectiveMastery,
  ProgressRecord,
} from './types';

export type SaveProgressInput = {
  student_id: number;
  topic_id: number;
  status: 'in_progress' | 'completed';
  score?: number | null;
  mastery_level?: string | null;
  time_spent_sec?: number;
  current_step?: number;
  max_opened_step?: number;
  answers?: Record<string, boolean>;
  responses?: Record<string, string>;
  attempts_by_step?: Record<string, number>;
  elapsed_time_sec?: number;
  objective_mastery?: Record<string, ObjectiveMastery>;
  objective_evidence?: Record<string, ObjectiveEvidence[]>;
  mastery_status?: MasteryStatus;
  lesson_version_id?: number | null;
  current_episode_id?: string | null;
  current_scene_id?: string | null;
  avatar_enabled?: boolean;
  audio_enabled?: boolean;
};

export const saveProgress = (data: SaveProgressInput) =>
  request<ProgressRecord>('/progress', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const getLessonProgress = async (
  studentId: number,
  topicId: number,
): Promise<ProgressRecord | null> => {
  return requestNullable<ProgressRecord>(`/progress/${studentId}/${topicId}`);
};

export const getStudentProgress = (studentId: number) =>
  request<ProgressRecord[]>(`/progress/${studentId}`);

export const useGetLessonProgress = (studentId: number, topicId: number, enabled = true) =>
  useQuery({
    queryKey: ['progress', studentId, topicId],
    queryFn: () => getLessonProgress(studentId, topicId),
    enabled: enabled && studentId > 0 && topicId > 0,
    staleTime: 30 * 1000,
    gcTime: 15 * 60 * 1000,
  });

export const useGetStudentProgress = (studentId: number, enabled = true) =>
  useQuery({
    queryKey: ['progress', studentId],
    queryFn: () => getStudentProgress(studentId),
    enabled: enabled && studentId > 0,
    staleTime: 60 * 1000,
    gcTime: 15 * 60 * 1000,
  });

export const useSaveProgress = () =>
  useMutation({
    mutationFn: saveProgress,
  });

export const useRestartLessonProgress = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, topicId }: { studentId: number; topicId: number }) =>
      request<ProgressRecord>(`/progress/${studentId}/${topicId}/restart`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.setQueryData(['progress', data.student_id, data.topic_id], data);
      queryClient.invalidateQueries({ queryKey: ['lesson-manifest', data.topic_id] });
      queryClient.invalidateQueries({ queryKey: ['curriculum-map'] });
      queryClient.invalidateQueries({ queryKey: ['subjects'] });
    },
  });
};

export type LessonAttempt = { id: number; attempt_number: number; completed_at: string; lesson_version_id: number | null; snapshot: ProgressRecord };
export const useLessonAttempts = (studentId: number, topicId: number, enabled: boolean) => useQuery({
  queryKey: ['lesson-attempts', studentId, topicId],
  queryFn: () => request<LessonAttempt[]>(`/progress/${studentId}/${topicId}/attempts`),
  enabled: enabled && studentId > 0,
});
