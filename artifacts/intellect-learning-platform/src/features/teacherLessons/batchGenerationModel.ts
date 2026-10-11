import type { BatchGenerationItem, LessonGenerationBatch, StartLessonBatchInput, Topic } from '@/lib/api';

export const MAX_BATCH_TOPICS = 30;
export const generationStatusLabels = {
  queued: 'В очереди', running: 'Создаётся', succeeded: 'Готово', failed: 'Ошибка', cancelled: 'Отменено',
} as const;

export function generationBlockReason(topic: Topic, active?: BatchGenerationItem): string | null {
  if (topic.archived_at) return 'Тема в архиве';
  if (topic.lesson_status === 'published' || topic.lesson_has_published_version) return 'У урока есть опубликованная версия';
  if (active?.status === 'queued' || active?.status === 'running') return 'Урок уже в очереди';
  if (!topic.learning_objectives?.trim()) return 'Добавьте цели обучения';
  return null;
}
export function hasDraftMaterials(topic: Topic): boolean {
  return Boolean(topic.lesson_has_materials ?? topic.lesson_id);
}
export function activeGenerationItems(batches: LessonGenerationBatch[]): Map<number, BatchGenerationItem> {
  const items = new Map<number, BatchGenerationItem>();
  for (const batch of batches) for (const item of batch.items) {
    if (item.status === 'queued' || item.status === 'running') items.set(item.topic_id, item);
  }
  return items;
}
export function batchFinishedCount(batch: LessonGenerationBatch): number {
  return batch.counts.succeeded + batch.counts.failed + batch.counts.cancelled;
}
export function retryableBatchTopics(batch: LessonGenerationBatch, topics: Topic[], active?: Map<number, BatchGenerationItem>): number[] {
  const available = new Map(topics.map(topic => [topic.id, topic]));
  return batch.items.filter(item => item.status === 'failed' && available.has(item.topic_id)
    && !generationBlockReason(available.get(item.topic_id)!, active?.get(item.topic_id))).map(item => item.topic_id);
}

export function selectGenerationTopics(ids: number[], topics: Topic[], active: Map<number, BatchGenerationItem>) {
  const available = new Map(topics.map(topic => [topic.id, topic]));
  const eligible = [...new Set(ids)].filter(id => {
    const topic = available.get(id);
    return topic && !generationBlockReason(topic, active.get(id));
  });
  return { ids: eligible.slice(0, MAX_BATCH_TOPICS), limited: eligible.length > MAX_BATCH_TOPICS };
}

// Reordering a selection must keep the same retry identity after an ambiguous network failure.
export function batchRequestFingerprint(input: Omit<StartLessonBatchInput, 'request_id'>): string {
  return JSON.stringify({ ...input, topic_ids: [...input.topic_ids].sort((a, b) => a - b) });
}
