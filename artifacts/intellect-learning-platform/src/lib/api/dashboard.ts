import { getAuthSession } from '../authSession';
import { useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { DashboardOverview, StudentSummary } from './types';

export function reportViewerKey() {
  const user = getAuthSession()?.user;
  return user ? `${user.profile_id}:${user.role}` : 'anonymous';
}

export const useDashboardOverview = () =>
  useQuery({ queryKey: ['dashboard-overview', reportViewerKey()], queryFn: () => request<DashboardOverview>('/dashboard/overview') });

export const useDashboardStudents = () =>
  useQuery({ queryKey: ['dashboard-students', reportViewerKey()], queryFn: () => request<StudentSummary[]>('/dashboard/students') });

export type StudentReportSummary = {
  completed: number; in_progress: number; average_score: number | null; needs_practice: number;
  total_published: number; completed_published: number; progress_percent: number;
};
export type StudentCompletedResult = {
  score: number | null; mastery_status: string; completed_at: string | null;
  elapsed_time_sec: number; lesson_version_id: number | null;
};
export type StudentReportLesson = {
  topic_id: number; name: string; status: string; mastery_status: string; score: number | null; completed_at: string | null;
  subject_id: number; subject_name: string; subject_grade: number; archived: boolean;
  published: boolean; historical: boolean; retrying: boolean; has_progress: boolean;
  started_at: string | null; updated_at: string | null; elapsed_time_sec: number;
  last_completed: StudentCompletedResult | null;
};
export type StudentReportSubject = { id: number; name: string; grade: number; summary: StudentReportSummary };
export type StudentLearningReport = {
  student_id: number; name: string; grade: number; summary: StudentReportSummary; subjects: StudentReportSubject[];
  skills: Array<{ id: number; name: string; status: string; mastery_score: number; evidence_count: number }>;
  lessons: StudentReportLesson[];
};
export type StudentReportQuestion = {
  key: string; block_index: number; question_index: number | null; component: string;
  stage: 'diagnostic' | 'practice' | 'assessment' | 'unknown'; prompt: string; response: string | null;
  outcome: string | null; expected: string | null; explanation: string | null; attempts: number | null; variant: string | null;
};
export type StudentAttemptDetail = StudentCompletedResult & {
  status: string; version_available: boolean;
  objectives: Array<{ id: string; text: string; status: string; score: number | null }>;
  questions: StudentReportQuestion[];
};
export type StudentLessonReport = {
  student_id: number; topic_id: number; name: string; current: StudentAttemptDetail | null; last_completed: StudentAttemptDetail | null;
};
export const useStudentLearningReport = (studentId: number | null) => useQuery({
  queryKey: ['student-learning-report', studentId, reportViewerKey()],
  queryFn: () => request<StudentLearningReport>(`/dashboard/students/${studentId}/learning`),
  enabled: studentId !== null,
});

export const useStudentLessonReport = (studentId: number, topicId: number | null) => useQuery({
  queryKey: ['student-lesson-report', studentId, topicId, reportViewerKey()],
  queryFn: () => request<StudentLessonReport>(`/dashboard/students/${studentId}/learning/lessons/${topicId}`),
  enabled: studentId > 0 && topicId !== null,
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
  queryKey: ['student-tutor-summary', studentId, reportViewerKey()],
  queryFn: () => request<StudentTutorSummary>(`/dashboard/students/${studentId}/tutor`),
  enabled: studentId !== null,
});
export const useStudentTutorDialogue = (studentId: number | null, topicId: number | null) => useQuery({
  queryKey: ['student-tutor-dialogue', studentId, topicId, reportViewerKey()],
  queryFn: () => request<StudentTutorDialogue>(`/dashboard/students/${studentId}/tutor/${topicId}`),
  enabled: studentId !== null && topicId !== null,
});
