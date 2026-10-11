import { describe, expect, it } from 'vitest';
import type { BatchGenerationItem, LessonGenerationBatch, Topic } from '@/lib/api';
import {
  activeGenerationItems, batchFinishedCount, batchRequestFingerprint,
  generationBlockReason, hasDraftMaterials, retryableBatchTopics, selectGenerationTopics,
} from './batchGenerationModel';

const topic = (id: number, overrides: Partial<Topic> = {}): Topic => ({
  id, section_id: 1, ktp_number: String(id), name: `Тема ${id}`, hours: 1,
  lesson_type: 'lesson', learning_objectives: 'Объяснить правило', skills: [], resources: null, ...overrides,
});
const item = (id: number, status: BatchGenerationItem['status']): BatchGenerationItem => ({
  job_id: `job-${id}`, topic_id: id, topic_name: `Тема ${id}`, status,
});
const batch = (items: BatchGenerationItem[]): LessonGenerationBatch => ({
  batch_id: 'batch-1', subject_id: 1, created_at: '2026-10-12T00:00:00Z', total: items.length,
  status: 'partial_failed', items,
  counts: { queued: 0, running: 0, succeeded: 0, failed: 0, cancelled: 0,
    ...Object.fromEntries(['queued', 'running', 'succeeded', 'failed', 'cancelled'].map(status => [status, items.filter(i => i.status === status).length])),
  },
});

describe('batch generation selection and progress', () => {
  it('excludes archive, absent objectives, published versions and active jobs', () => {
    const topics = [topic(1), topic(2, { archived_at: 'now' }), topic(3, { learning_objectives: '  ' }),
      topic(4, { lesson_status: 'published' }), topic(5, { lesson_status: 'draft', lesson_has_published_version: true }), topic(6), topic(7)];
    const active = new Map([[6, item(6, 'queued')], [7, item(7, 'running')]]);
    expect(selectGenerationTopics(topics.map(t => t.id), topics, active).ids).toEqual([1]);
    expect(generationBlockReason(topic(1), item(1, 'failed'))).toBeNull();
  });

  it('caps a batch at 30 and preserves existing choices when a further topic is added', () => {
    const topics = Array.from({ length: 31 }, (_, index) => topic(index + 1));
    const selected = topics.slice(1).map(t => t.id);
    expect(selectGenerationTopics([...selected, 1, 999, 2], topics, new Map())).toEqual({ ids: selected, limited: true });
  });

  it('deduplicates choices and drops deleted topics without reporting an artificial limit', () => {
    expect(selectGenerationTopics([1, 2, 1, 999], [topic(1), topic(2)], new Map())).toEqual({ ids: [1, 2], limited: false });
  });

  it('treats reserved empty lesson rows as topics without materials', () => {
    expect(hasDraftMaterials(topic(1, { lesson_id: 42, lesson_has_materials: false }))).toBe(false);
    expect(hasDraftMaterials(topic(2, { lesson_id: 42, lesson_has_materials: true }))).toBe(true);
    expect(hasDraftMaterials(topic(3, { lesson_id: 42 }))).toBe(true);
    expect(hasDraftMaterials(topic(4))).toBe(false);
  });

  it('restores only active items as selection blockers and counts partial failures/cancellations', () => {
    const data = batch([item(1, 'queued'), item(2, 'running'), item(3, 'succeeded'), item(4, 'failed'), item(5, 'cancelled')]);
    expect([...activeGenerationItems([data]).keys()]).toEqual([1, 2]);
    expect(batchFinishedCount(data)).toBe(3);
  });

  it('selects failed topics for an explicit retry but skips deleted, published and newly active topics', () => {
    const data = batch([item(1, 'failed'), item(2, 'failed'), item(3, 'failed'), item(4, 'failed'), item(5, 'succeeded')]);
    const topics = [topic(1), topic(2, { lesson_status: 'published' }), topic(4), topic(5)];
    expect(retryableBatchTopics(data, topics, new Map([[4, item(4, 'queued')]]))).toEqual([1]);
  });

  it('keeps retry identity when the same topic set is reordered, and changes it for different options', () => {
    const input = { subject_id: 1, topic_ids: [2, 1], teacher_id: 7, model: 'model-a', content_language: 'ky' as const, replace_existing_drafts: false };
    expect(batchRequestFingerprint(input)).toBe(batchRequestFingerprint({ ...input, topic_ids: [1, 2] }));
    for (const change of [{ model: 'model-b' }, { replace_existing_drafts: true }, { topic_ids: [1] }, { teacher_id: 8 }]) {
      expect(batchRequestFingerprint({ ...input, ...change })).not.toBe(batchRequestFingerprint(input));
    }
    expect(input.topic_ids).toEqual([2, 1]);
  });
});
