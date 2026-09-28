import { request } from './client';
import type { Block, GeneratedLesson } from './types';

export type ComponentSource = {
  section_id: number;
  title: string;
  page_from?: number | null;
  page_to?: number | null;
  items: Array<{ id: number; label?: string | null; kind: string; page?: number | null }>;
};

export type LessonComponentContext = {
  revision: string;
  objectives: Array<{ id: string; text: string }>;
  sources: ComponentSource[];
  reason?: string | null;
  supported_components?: string[];
};

export type PrepareLessonComponentInput = {
  component: string;
  objective_id: string;
  after_index: number | null;
  base_revision: string;
  source_item_id: number | null;
  source_section_id: number | null;
  model?: string;
};

export type PreparedLessonComponent = {
  block: Block;
  base_revision: string;
  context_fingerprint: string;
  source_label: string;
  warnings: string[];
};

export const componentContextKey = (lessonId: number) => ['lesson-component-context', lessonId] as const;

export const getLessonComponentContext = (lessonId: number) =>
  request<LessonComponentContext>(`/lessons/${lessonId}/components/context`);

export const prepareLessonComponent = (lessonId: number, input: PrepareLessonComponentInput) =>
  request<PreparedLessonComponent>(`/lessons/${lessonId}/components/prepare`, {
    method: 'POST', body: JSON.stringify(input),
  });

export const insertLessonComponent = (
  lessonId: number,
  input: Pick<PreparedLessonComponent, 'block' | 'base_revision' | 'context_fingerprint'> & {
    after_index: number | null;
    request_id: string;
  },
) => request<GeneratedLesson>(`/lessons/${lessonId}/components/insert`, {
  method: 'POST', body: JSON.stringify(input),
});
