import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { readPersistentRequestCache, request, requestCached } from './client';
import type { Section, SectionOutline, Subject, Topic } from './types';

const studentParam = (studentId?: number) => studentId ? `?student_id=${studentId}` : '';
const SUBJECTS_CACHE_MS = 2 * 60 * 1000;
const OUTLINE_CACHE_MS = 5 * 60 * 1000;
const subjectsPath = (studentId?: number) => `/subjects${studentParam(studentId)}`;
const sectionsPath = (subjectId: number, studentId?: number) =>
  `/subjects/${subjectId}/sections${studentParam(studentId)}`;

export const useSubjects = (studentId?: number) =>
  useQuery({
    queryKey: ['subjects', studentId ?? 'teacher'],
    queryFn: () => requestCached<Subject[]>(subjectsPath(studentId), SUBJECTS_CACHE_MS),
    initialData: () => readPersistentRequestCache<Subject[]>(subjectsPath(studentId))?.data,
    initialDataUpdatedAt: () => readPersistentRequestCache<Subject[]>(subjectsPath(studentId))?.updatedAt,
    staleTime: SUBJECTS_CACHE_MS,
    gcTime: 15 * 60 * 1000,
  });

export const useSections = (subjectId: number, enabled = true, studentId?: number) =>
  useQuery({
    queryKey: ['sections', subjectId, studentId ?? 'teacher'],
    queryFn: () => requestCached<Section[]>(sectionsPath(subjectId, studentId), OUTLINE_CACHE_MS),
    enabled: enabled && subjectId > 0,
    initialData: () => readPersistentRequestCache<Section[]>(sectionsPath(subjectId, studentId))?.data,
    initialDataUpdatedAt: () => readPersistentRequestCache<Section[]>(sectionsPath(subjectId, studentId))?.updatedAt,
    staleTime: OUTLINE_CACHE_MS,
    gcTime: 30 * 60 * 1000,
  });

export type TopicInput = {
  name: string; lesson_type: string; learning_objectives?: string; hours?: number;
  covered_topic_ids?: number[]; source_assessment_topic_id?: number | null;
};
export const useTopic = (topicId: number) => useQuery({
  queryKey: ['topic', topicId], queryFn: () => request<Topic>(`/topics/${topicId}`), enabled: topicId > 0,
});
export const useTeacherOutline = (subjectId: number, includeArchived = false) => useQuery({
  queryKey: ['subject-outline', subjectId, 'teacher', includeArchived],
  queryFn: () => request<SectionOutline[]>(`/subjects/${subjectId}/outline?include_archived=${includeArchived}`), enabled: subjectId > 0,
});
export const catalogInvalidationKeys = [
  ['subjects'], ['sections'], ['topics'], ['topic'], ['subject-outline'], ['curriculum-graph'], ['curriculum-map'], ['dashboard'], ['progress'],
];
export function useSaveTopic() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ sectionId, topicId, data }: { sectionId: number; topicId?: number; data: TopicInput }) =>
      request<Topic>(topicId ? `/topics/${topicId}` : `/sections/${sectionId}/topics`, { method: topicId ? 'PATCH' : 'POST', body: JSON.stringify(data) }),
    onSuccess: async () => { await Promise.all(catalogInvalidationKeys.map(queryKey => client.invalidateQueries({ queryKey }))); },
  });
}
export function useArchiveTopic() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ topicId, restore }: { topicId: number; restore?: boolean }) => request<Topic>(`/topics/${topicId}/${restore ? 'restore' : 'archive'}`, { method: 'POST' }),
    onSuccess: async () => { await Promise.all([...catalogInvalidationKeys, ['lesson'], ['lesson-status'], ['lesson-manifest']].map(queryKey => client.invalidateQueries({ queryKey }))); },
  });
}

export function useCreateCourse() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (data: { name: string; grade: number }) => request<Subject>('/subjects', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['subjects'] }) });
}
export function useCreateSection() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (data: { subjectId: number; name: string }) => request<Section>(`/subjects/${data.subjectId}/sections`, { method: 'POST', body: JSON.stringify({ name: data.name }) }),
    onSuccess: async () => { await Promise.all(catalogInvalidationKeys.map(queryKey => client.invalidateQueries({ queryKey }))); } });
}
export function useRenameSubject() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (data: { subjectId: number; name: string }) => request<Subject>(`/subjects/${data.subjectId}`, { method: 'PATCH', body: JSON.stringify({ name: data.name }) }),
    onSuccess: async () => { await Promise.all(catalogInvalidationKeys.map(queryKey => client.invalidateQueries({ queryKey }))); } });
}
