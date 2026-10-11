import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from './client';
import { cancelLessonGenerationBatch, getLessonGenerationBatches, startLessonGenerationBatch } from './batchLessonGeneration';

vi.mock('./client', () => ({ request: vi.fn() }));

describe('server batch generation API', () => {
  beforeEach(() => { vi.mocked(request).mockReset(); });

  it('sends one batch with selected topics, retry identity and shared generation options', async () => {
    const input = { subject_id: 7, topic_ids: [12, 13], teacher_id: 3, request_id: 'reusable-id',
      model: 'selected-model', content_language: 'ky' as const, replace_existing_drafts: true };
    const result = { batch_id: input.request_id, items: [] };
    vi.mocked(request).mockResolvedValue(result);
    await expect(startLessonGenerationBatch(input)).resolves.toEqual(result);
    expect(request).toHaveBeenCalledExactlyOnceWith('/lessons/generate/batch', { method: 'POST', body: JSON.stringify(input) });
  });

  it('loads queue state from the server without a stored browser batch id', async () => {
    vi.mocked(request).mockResolvedValue([{ batch_id: 'restored' }]);
    await expect(getLessonGenerationBatches(7)).resolves.toEqual([{ batch_id: 'restored' }]);
    expect(request).toHaveBeenCalledExactlyOnceWith('/lessons/generate/batches?subject_id=7');
  });

  it('requests cancellation for the selected subject and safely encodes the batch id', async () => {
    await cancelLessonGenerationBatch(7, 'batch/id');
    expect(request).toHaveBeenCalledExactlyOnceWith('/lessons/generate/batches/batch%2Fid/cancel?subject_id=7', { method: 'POST' });
  });

  it('does not automatically resubmit a failed mutation', async () => {
    const failure = new TypeError('Connection lost');
    vi.mocked(request).mockRejectedValue(failure);
    let caught: unknown;
    try {
      await startLessonGenerationBatch({ subject_id: 7, topic_ids: [12], teacher_id: 3, request_id: 'same-on-user-retry' });
    } catch (error) { caught = error; }
    expect(caught).toBe(failure);
    expect(request).toHaveBeenCalledTimes(1);
  });
});
