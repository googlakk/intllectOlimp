import { useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { DashboardOverview, StudentSummary } from './types';

export const useDashboardOverview = () =>
  useQuery({ queryKey: ['dashboard-overview'], queryFn: () => request<DashboardOverview>('/dashboard/overview') });

export const useDashboardStudents = () =>
  useQuery({ queryKey: ['dashboard-students'], queryFn: () => request<StudentSummary[]>('/dashboard/students') });

export type StudentLearningReport = { student_id: number; name: string; skills: Array<{ id: number; name: string; status: string; mastery_score: number; evidence_count: number }>; lessons: Array<{ topic_id: number; name: string; status: string; mastery_status: string; score: number | null; archived: boolean }> };
export const useStudentLearningReport = (studentId: number | null) => useQuery({
  queryKey: ['student-learning-report', studentId],
  queryFn: () => request<StudentLearningReport>(`/dashboard/students/${studentId}/learning`),
  enabled: studentId !== null,
});
