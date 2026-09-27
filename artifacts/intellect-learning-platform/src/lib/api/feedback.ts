import { useMutation, useQuery } from '@tanstack/react-query';

import { request } from './client';

export type LessonFeedbackInput = {
  topic_id: number;
  rating?: number | null;
  had_errors?: boolean | null;
  comment?: string | null;
};

export type LessonFeedbackItem = {
  id: number;
  created_at: string | null;
  rating: number | null;
  had_errors: boolean | null;
  comment: string | null;
  student_id: number;
  student_name: string;
  topic_id: number;
  topic_name: string;
  subject_id: number;
  subject_name: string;
  grade: number;
  lesson_version_id: number | null;
};

export type LessonFeedbackList = {
  available: boolean;
  summary: { total: number; average_rating: number | null; with_errors: number };
  items: LessonFeedbackItem[];
};

export const useSubmitLessonFeedback = () => useMutation({
  mutationFn: (data: LessonFeedbackInput) =>
    request<{ saved: boolean }>('/feedback', { method: 'POST', body: JSON.stringify(data) }),
});

export const useLessonFeedbackList = (onlyErrors: boolean) => useQuery({
  queryKey: ['admin-feedback', onlyErrors],
  queryFn: () => request<LessonFeedbackList>(`/admin/feedback${onlyErrors ? '?only_errors=true' : ''}`),
});
