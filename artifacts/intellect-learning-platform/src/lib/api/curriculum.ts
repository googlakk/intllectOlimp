import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { readPersistentRequestCache, request, requestCached } from './client';
import type { CurriculumGraph, CurriculumMap } from './types';

const CURRICULUM_MAP_CACHE_MS = 2 * 60 * 1000;

export const curriculumMapPath = (studentId: number, subjectId?: number) =>
  `/curriculum/students/${studentId}/map${subjectId ? `?subject_id=${subjectId}` : ''}`;

export const useCurriculumMap = (studentId: number, subjectId?: number, enabled = true) =>
  useQuery({
    queryKey: ['curriculum-map', studentId, subjectId ?? 'all'],
    queryFn: () => requestCached<CurriculumMap>(curriculumMapPath(studentId, subjectId), CURRICULUM_MAP_CACHE_MS),
    enabled: enabled && studentId > 0,
    initialData: () => readPersistentRequestCache<CurriculumMap>(curriculumMapPath(studentId, subjectId))?.data,
    initialDataUpdatedAt: () => readPersistentRequestCache<CurriculumMap>(curriculumMapPath(studentId, subjectId))?.updatedAt,
    staleTime: CURRICULUM_MAP_CACHE_MS,
    gcTime: 15 * 60 * 1000,
  });

export const useCurriculumGraph = (subjectId: number, enabled = true) =>
  useQuery({
    queryKey: ['curriculum-graph', subjectId],
    queryFn: () => request<CurriculumGraph>(`/curriculum/subjects/${subjectId}/graph`),
    enabled: enabled && subjectId > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

export const useBuildCurriculumGraph = (subjectId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => request<{ topics: number; skills: number; edges: number }>(`/curriculum/subjects/${subjectId}/build`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['curriculum-graph', subjectId] }),
  });
};
