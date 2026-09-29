import { useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { DashboardOverview, StudentSummary } from './types';

export const useDashboardOverview = () =>
  useQuery({ queryKey: ['dashboard-overview'], queryFn: () => request<DashboardOverview>('/dashboard/overview') });

export const useDashboardStudents = () =>
  useQuery({ queryKey: ['dashboard-students'], queryFn: () => request<StudentSummary[]>('/dashboard/students') });

export type StudentLearningReport = { student_id: number; name: string; skills: Array<{ id: number; name: string; status: string; mastery_score: number; evidence_count: number }>; lessons: Array<{
  topic_id: number; name: string; status: string; mastery_status: string; score: number | null; completed_at: string | null;
  subject_id: number; subject_name: string; subject_grade: number; archived: boolean;
}> };
export const useStudentLearningReport = (studentId: number | null) => useQuery({
  queryKey: ['student-learning-report', studentId],
  queryFn: () => request<StudentLearningReport>(`/dashboard/students/${studentId}/learning`),
  enabled: studentId !== null,
});

export type StudentTutorTopic = {
  topic_id: number; name: string; turns: number; messages: number; hints: number;
  leaks_blocked: number; teacher_calls: number; safety_flags: number; last_at: string | null;
};
export type StudentTutorAlert = { topic_id: number; turn_id: number; created_at: string | null; kind: 'distress' | 'call_teacher'; student_text: string | null };
export type StudentTutorSummary = {
  available: boolean;
  topics: StudentTutorTopic[];
  misconceptions: Array<{ code: string; count: number }>;
  alerts: StudentTutorAlert[];
};
export type StudentTutorTurn = {
  id: number; created_at: string | null; lesson_version_id: number | null; block_index: number; question_index: number | null;
  event: string; student_text: string | null; student_value: string | null; check_outcome: string | null;
  reply: string; source: string; action: string | null; misconception_code: string | null; diagnosis: string | null;
  safety_flag: string; off_topic: boolean; leak_blocked: boolean;
};
export type StudentTutorDialogue = { available: boolean; topic_id: number; turns: StudentTutorTurn[] };

export const useStudentTutorSummary = (studentId: number | null) => useQuery({
  queryKey: ['student-tutor-summary', studentId],
  queryFn: () => request<StudentTutorSummary>(`/dashboard/students/${studentId}/tutor`),
  enabled: studentId !== null,
});
export const useStudentTutorDialogue = (studentId: number | null, topicId: number | null) => useQuery({
  queryKey: ['student-tutor-dialogue', studentId, topicId],
  queryFn: () => request<StudentTutorDialogue>(`/dashboard/students/${studentId}/tutor/${topicId}`),
  enabled: studentId !== null && topicId !== null,
});
