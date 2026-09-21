import { useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { Section, SectionOutline, Subject, Topic } from './types';

export const useSubjects = () =>
  useQuery({ queryKey: ['subjects'], queryFn: () => request<Subject[]>('/subjects') });

export const useSections = (subjectId: number, enabled = true) =>
  useQuery({
    queryKey: ['sections', subjectId],
    queryFn: () => request<Section[]>(`/subjects/${subjectId}/sections`),
    enabled: enabled && subjectId > 0,
  });

export const useSubjectOutline = (subjectId: number, enabled = true) =>
  useQuery({
    queryKey: ['subject-outline', subjectId],
    queryFn: () => request<SectionOutline[]>(`/subjects/${subjectId}/outline`),
    enabled: enabled && subjectId > 0,
  });

export const useTopics = (sectionId: number, enabled = true) =>
  useQuery({
    queryKey: ['topics', sectionId],
    queryFn: () => request<Topic[]>(`/sections/${sectionId}/topics`),
    enabled: enabled && sectionId > 0,
  });
