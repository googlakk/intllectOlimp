import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { request } from './client';
import type { InstructionLanguage } from '@/lib/languages';

export type GenerationItemStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type BatchGenerationItem = {
  job_id: string | null; topic_id: number; topic_name: string; status: GenerationItemStatus;
  error?: string | null; lesson_id?: number | null;
};
export type LessonGenerationBatch = {
  batch_id: string; subject_id: number; created_at: string;
  status: GenerationItemStatus | 'partial_failed'; total: number;
  counts: Record<GenerationItemStatus, number>; items: BatchGenerationItem[];
};
export type StartLessonBatchInput = {
  subject_id: number; topic_ids: number[]; teacher_id: number; request_id: string;
  model?: string; content_language?: InstructionLanguage; replace_existing_drafts?: boolean;
};
export const generationBatchKey = (subjectId: number) => ['lesson-generation-batches', subjectId] as const;
export const getLessonGenerationBatches = (subjectId: number) =>
  request<LessonGenerationBatch[]>(`/lessons/generate/batches?subject_id=${subjectId}`);
export const startLessonGenerationBatch = (input: StartLessonBatchInput) =>
  request<LessonGenerationBatch>('/lessons/generate/batch', { method: 'POST', body: JSON.stringify(input) });
export const cancelLessonGenerationBatch = (subjectId: number, batchId: string) =>
  request<LessonGenerationBatch>(`/lessons/generate/batches/${encodeURIComponent(batchId)}/cancel?subject_id=${subjectId}`, { method: 'POST' });

export function useLessonGenerationBatches(subjectId: number) {
  return useQuery({
    queryKey: generationBatchKey(subjectId), queryFn: () => getLessonGenerationBatches(subjectId),
    enabled: subjectId > 0,
    refetchInterval: query => query.state.data?.some(batch => batch.counts.queued + batch.counts.running > 0) ? 3000 : 15000,
    refetchOnWindowFocus: true,
  });
}
export function useStartLessonGenerationBatch(subjectId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: startLessonGenerationBatch, retry: false,
    onSuccess: batch => client.setQueryData<LessonGenerationBatch[]>(generationBatchKey(subjectId), previous =>
      [batch, ...(previous || []).filter(item => item.batch_id !== batch.batch_id)]),
    onSettled: () => client.invalidateQueries({ queryKey: generationBatchKey(subjectId) }),
  });
}
export function useCancelLessonGenerationBatch(subjectId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => cancelLessonGenerationBatch(subjectId, batchId), retry: false,
    onSuccess: () => client.invalidateQueries({ queryKey: generationBatchKey(subjectId) }),
  });
}
