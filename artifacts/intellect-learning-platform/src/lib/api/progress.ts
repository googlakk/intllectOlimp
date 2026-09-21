import { useMutation, useQuery } from '@tanstack/react-query';

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
  attempts_by_step?: Record<string, number>;
  elapsed_time_sec?: number;
  objective_mastery?: Record<string, ObjectiveMastery>;
  objective_evidence?: Record<string, ObjectiveEvidence[]>;
  mastery_status?: MasteryStatus;
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
  });

export const useGetStudentProgress = (studentId: number, enabled = true) =>
  useQuery({
    queryKey: ['progress', studentId],
    queryFn: () => getStudentProgress(studentId),
    enabled: enabled && studentId > 0,
  });

export const useSaveProgress = () =>
  useMutation({
    mutationFn: saveProgress,
  });
