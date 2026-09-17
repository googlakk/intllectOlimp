import { useMutation, useQuery } from '@tanstack/react-query';

export type User = { id: number; name: string; role: 'student' | 'teacher'; grade: number | null };
export type LoginUsers = { students: User[]; teachers: User[] };
export type Subject = { id: number; name: string; grade: number; hours_per_week: number; hours_per_year: number; source_info: string | null; instruction_language?: 'ru' | 'ky'; progress?: number };
export type Section = { id: number; subject_id: number; name: string; sort_order: number; total_hours: number };
export type Topic = { id: number; section_id: number; ktp_number: string | null; name: string; hours: number; lesson_type: string; learning_objectives: string | null; skills: string[]; resources: string | null };
export type LearningObjective = {
  id: string;
  text: string;
  success_criteria?: string;
};
export type ObjectiveEvidence = {
  objective_id: string;
  block_index?: number;
  stage?: 'diagnostic' | 'explanation' | 'practice' | 'assessment' | string;
  correct?: boolean;
  score?: number;
  attempts?: number;
};
export type MasteryStatus = 'not_assessed' | 'in_progress' | 'mastered' | 'needs_practice';
export type ObjectiveMastery = {
  status: MasteryStatus;
  score?: number;
  diagnostic_passed?: boolean;
  final_passed?: boolean;
};
export type QualityReport = {
  publishable?: boolean;
  objectives?: Record<string, {
    objective?: string;
    diagnostic?: number[];
    explanation?: number[];
    practice?: number[];
    assessment?: number[];
    evidence?: Array<{ block: number; stage: string }>;
  }>;
  gaps?: Array<{ objective_id?: string; objective?: string; missing?: string[] } | string>;
  errors?: Array<{ code?: string; block?: number; message?: string } | string>;
  warnings?: Array<{ code?: string; block?: number; message?: string } | string>;
  legacy?: boolean;
};
export type ObjectiveResult = {
  status: MasteryStatus;
  score?: number;
  evidence?: ObjectiveEvidence[];
};
export type ProgressRecord = { id: number; student_id: number; topic_id: number; status: 'not_started' | 'in_progress' | 'completed'; score: number | null; mastery_level: string | null; mastery_status?: MasteryStatus; objective_mastery?: Record<string, ObjectiveMastery>; objective_evidence?: Record<string, ObjectiveEvidence[]>; time_spent_sec: number; attempts: number; current_step: number; max_opened_step: number; answers: Record<string, boolean>; attempts_by_step: Record<string, number>; elapsed_time_sec: number; };
export type DashboardOverview = { students: number; subjects: number; topics: number; published_lessons: number; average_progress: number };
export type StudentSummary = { id: number; name: string; grade: number; completed_topics: number; average_score: number };
export type ComponentSchema = {
  type?: string;
  enum?: string[];
  required?: string[];
  minItems?: number;
  maxItems?: number;
  properties?: Record<string, ComponentSchema>;
  items?: ComponentSchema;
};
export type ComponentRegistryEntry = {
  id: string;
  code: string;
  category: string;
  subjects: string[];
  purpose: string;
  is_assessment: boolean;
  content_schema: ComponentSchema;
  rendering_notes: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
    throw new Error(formatApiDetail(body.detail ?? body));
  }
  return response.json() as Promise<T>;
}

export function formatApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(formatApiDetail).filter(Boolean).join('; ');
  if (detail && typeof detail === 'object') {
    const value = detail as Record<string, unknown>;
    const primary = value.message ?? value.detail ?? value.error;
    const quality = value.quality;
    const qualityText = quality && typeof quality === 'object'
      ? formatApiDetail((quality as Record<string, unknown>).errors || (quality as Record<string, unknown>).gaps)
      : '';
    return [primary ? formatApiDetail(primary) : '', qualityText].filter(Boolean).join(' — ') || JSON.stringify(detail);
  }
  return detail == null ? 'Ошибка сервера' : String(detail);
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

export const useComponents = () =>
  useQuery({
    queryKey: ['components'],
    queryFn: () => request<ComponentRegistryEntry[]>('/components'),
  });
export type Block = {
  component: string;
  content: Record<string, unknown>;
};

export type GeneratedLesson = {
  id: number;
  topic_id: number;
  blocks: Block[];
  lesson_metadata: Record<string, unknown> & {
    objectives?: LearningObjective[];
    quality_report?: QualityReport;
    legacy_review_required?: boolean;
  };
  status: 'draft' | 'published';
  generated_at: string;
  published_at: string | null;
  published_by: number | null;
  model_used: string | null;
};

export async function getLessonByTopic(
  topicId: number,
  role?: 'student' | 'teacher',
): Promise<GeneratedLesson | null> {
  const response = await fetch(`/api/lessons/${topicId}${role ? `?role=${role}` : ''}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
    throw new Error(formatApiDetail(body.detail ?? body));
  }
  return response.json() as Promise<GeneratedLesson>;
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

export const uploadKtp = (data: unknown) =>
  request<Subject & { section_count: number; topic_count: number }>('/ktp/upload', {
    method: 'POST',
    body: JSON.stringify(data),
  });

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

export const saveProgress = (
  data: {
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
  }
) =>
  request<ProgressRecord>('/progress', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const getLessonProgress = async (studentId: number, topicId: number): Promise<ProgressRecord | null> => {
  const response = await fetch(`/api/progress/${studentId}/${topicId}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
    throw new Error(formatApiDetail(body.detail ?? body));
  }
  return response.json() as Promise<ProgressRecord>;
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
    mutationFn: (data: Parameters<typeof saveProgress>[0]) =>
      saveProgress(data),
  });

export const useLessonStatus = (topicId: number, enabled = true) =>
  useQuery({
    queryKey: ['lesson-status', topicId],
    queryFn: () => getLessonByTopic(topicId, 'teacher'),
    enabled: enabled && topicId > 0,
  });
