import { useMutation, useQuery } from '@tanstack/react-query';

export type User = { id: number; name: string; role: 'student' | 'teacher'; grade: number | null };
export type LoginUsers = { students: User[]; teachers: User[] };
export type Subject = { id: number; name: string; grade: number; hours_per_week: number; hours_per_year: number; source_info: string | null; progress?: number };
export type Section = { id: number; subject_id: number; name: string; sort_order: number; total_hours: number };
export type Topic = { id: number; section_id: number; ktp_number: string | null; name: string; hours: number; lesson_type: string; learning_objectives: string | null; skills: string[]; resources: string | null };
export type ProgressRecord = { id: number; student_id: number; topic_id: number; status: string; score: number | null; mastery_level: string | null; time_spent_sec: number; attempts: number };
export type DashboardOverview = { students: number; subjects: number; topics: number; published_lessons: number; average_progress: number };
export type StudentSummary = { id: number; name: string; grade: number; completed_topics: number; average_score: number };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
    throw new Error(body.detail ?? 'Ошибка сервера');
  }
  return response.json() as Promise<T>;
}

export const useLoginUsers = () =>
  useQuery({ queryKey: ['login-users'], queryFn: () => request<LoginUsers>('/auth/users') });

export const useLogin = () =>
  useMutation({ mutationFn: (data: { role: 'student' | 'teacher'; name: string }) =>
    request<User>('/auth/login', { method: 'POST', body: JSON.stringify(data) }) });

export const useSubjects = () =>
  useQuery({ queryKey: ['subjects'], queryFn: () => request<Subject[]>('/subjects') });

export const useSections = (subjectId: number, enabled = true) =>
  useQuery({ queryKey: ['sections', subjectId], queryFn: () => request<Section[]>(`/subjects/${subjectId}/sections`), enabled: enabled && subjectId > 0 });

export const useTopics = (sectionId: number, enabled = true) =>
  useQuery({ queryKey: ['topics', sectionId], queryFn: () => request<Topic[]>(`/sections/${sectionId}/topics`), enabled: enabled && sectionId > 0 });

export const useUploadKtp = () =>
  useMutation({ mutationFn: (data: unknown) => request<{ status: string }>('/ktp/upload', { method: 'POST', body: JSON.stringify(data) }) });

export const useDashboardOverview = () =>
  useQuery({ queryKey: ['dashboard-overview'], queryFn: () => request<DashboardOverview>('/dashboard/overview') });

export const useDashboardStudents = () =>
  useQuery({ queryKey: ['dashboard-students'], queryFn: () => request<StudentSummary[]>('/dashboard/students') });