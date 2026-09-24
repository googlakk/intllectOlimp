import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { request } from './client';

export type Classroom = {
  id: number; name: string; grade: number; academic_year: string; student_count: number;
  teachers: Array<{ profile_id: number; name: string; status: string }>;
};
export type ClassroomStudent = {
  student_id: number; profile_id: number; name: string; login: string; grade: number;
  status: 'active' | 'blocked' | 'invited' | 'archived'; must_change_password: boolean; enrolled_at: string;
};
export type TeacherAccount = {
  teacher_id: number; profile_id: number; name: string; login: string;
  status: string; must_change_password: boolean;
};
export type IssuedCredentials = {
  profile_id: number; login: string; temporary_password: string; student_id?: number; teacher_id?: number; classroom_id?: number;
};

export const useClassrooms = () => useQuery({
  queryKey: ['accounts', 'classrooms'],
  queryFn: () => request<Classroom[]>('/accounts/classrooms'),
});

export const useClassroomStudents = (classroomId: number | null) => useQuery({
  queryKey: ['accounts', 'classrooms', classroomId, 'students'],
  queryFn: () => request<ClassroomStudent[]>(`/accounts/classrooms/${classroomId}/students`),
  enabled: Boolean(classroomId),
});

export const useTeachers = (enabled = true) => useQuery({
  queryKey: ['accounts', 'teachers'],
  queryFn: () => request<TeacherAccount[]>('/accounts/teachers'),
  enabled,
});

function useRefreshingMutation<TInput, TResult>(
  mutationFn: (input: TInput) => Promise<TResult>,
  keys: string[][],
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => keys.forEach((key) => client.invalidateQueries({ queryKey: key })),
  });
}

export const useCreateClassroom = () => useRefreshingMutation(
  (data: { name: string; grade: number; academic_year: string }) => request<Classroom>('/accounts/classrooms', { method: 'POST', body: JSON.stringify(data) }),
  [['accounts', 'classrooms']],
);

export const useCreateTeacher = () => useRefreshingMutation(
  (data: { login: string; display_name: string }) => request<IssuedCredentials>('/accounts/teachers', { method: 'POST', body: JSON.stringify(data) }),
  [['accounts', 'teachers']],
);

export const useCreateStudent = () => useRefreshingMutation(
  (data: { classroom_id: number; login: string; display_name: string }) => request<IssuedCredentials>('/accounts/students', { method: 'POST', body: JSON.stringify(data) }),
  [['accounts', 'classrooms']],
);

export const useAssignTeacher = () => useRefreshingMutation(
  (data: { classroom_id: number; teacher_profile_id: number }) => request<{ ok: boolean }>(`/accounts/classrooms/${data.classroom_id}/teachers`, { method: 'POST', body: JSON.stringify({ teacher_profile_id: data.teacher_profile_id }) }),
  [['accounts', 'classrooms']],
);

export const useUnassignTeacher = () => useRefreshingMutation(
  (data: { classroom_id: number; teacher_profile_id: number }) => request<{ ok: boolean }>(`/accounts/classrooms/${data.classroom_id}/teachers/${data.teacher_profile_id}`, { method: 'DELETE' }),
  [['accounts', 'classrooms']],
);

export const useResetAccountPassword = () => useMutation({
  mutationFn: (profileId: number) => request<{ temporary_password: string }>(`/accounts/${profileId}/reset-password`, { method: 'POST' }),
});

export const useSetAccountBlocked = () => useRefreshingMutation(
  (data: { profileId: number; blocked: boolean }) => request<{ ok: boolean }>(`/accounts/${data.profileId}/${data.blocked ? 'block' : 'restore'}`, { method: 'POST' }),
  [['accounts', 'classrooms'], ['accounts', 'teachers']],
);

export const useBulkCreateStudents = () => useRefreshingMutation(
  (data: { classroom_id: number; students: Array<{ login: string; display_name: string }> }) =>
    request<{ created: IssuedCredentials[]; errors: Array<{ row: number; login: string; error: string }> }>('/accounts/students/bulk', {
      method: 'POST', body: JSON.stringify(data),
    }),
  [['accounts', 'classrooms']],
);

export const useTransferStudent = () => useRefreshingMutation(
  (data: { profileId: number; target_classroom_id: number }) => request<{ ok: boolean }>(`/accounts/students/${data.profileId}/transfer`, {
    method: 'POST', body: JSON.stringify({ target_classroom_id: data.target_classroom_id }),
  }),
  [['accounts', 'classrooms']],
);
