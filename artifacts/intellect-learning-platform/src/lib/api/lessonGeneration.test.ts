import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './client';
import { generateLesson } from './lessonGeneration';
import type { GeneratedLesson } from './types';

vi.mock('./client', async importOriginal => ({
  ...await importOriginal<typeof import('./client')>(),
  request: vi.fn(),
}));

const running = { job_id: 'job-1', topic_id: 780, status: 'running' };
const lesson = { id: 42, topic_id: 780, blocks: [] } as unknown as GeneratedLesson;
const succeeded = { ...running, status: 'succeeded', lesson };

describe('background lesson generation', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.mocked(request).mockReset(); });
  afterEach(() => { vi.useRealTimers(); });

  it('starts once, polls until ready and returns the generated lesson', async () => {
    vi.mocked(request).mockResolvedValueOnce(running).mockResolvedValueOnce(running).mockResolvedValueOnce(succeeded);
    const result = generateLesson(780, 3, 'selected-model', 'ky');
    await vi.runAllTimersAsync();
    await expect(result).resolves.toEqual(lesson);
    const [path, init] = vi.mocked(request).mock.calls[0];
    expect(path).toBe('/lessons/generate/start');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({
      topic_id: 780, teacher_id: 3, model: 'selected-model', content_language: 'ky', request_id: expect.any(String),
    });
    expect(vi.mocked(request).mock.calls.slice(1)).toEqual([
      ['/lessons/generate/status/job-1?topic_id=780'],
      ['/lessons/generate/status/job-1?topic_id=780'],
    ]);
  });

  it('retries a temporary status-read failure without repeating generation', async () => {
    vi.mocked(request).mockResolvedValueOnce(running).mockRejectedValueOnce(new ApiError(524, 'timeout')).mockResolvedValueOnce(succeeded);
    const result = generateLesson(780, 3);
    await vi.runAllTimersAsync();
    await expect(result).resolves.toEqual(lesson);
    expect(vi.mocked(request).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });

  it('waits while a single lesson is queued behind batch work, then returns the result', async () => {
    vi.mocked(request).mockResolvedValueOnce({ ...running, status: 'queued' })
      .mockResolvedValueOnce({ ...running, status: 'queued' }).mockResolvedValueOnce(running).mockResolvedValueOnce(succeeded);
    const result = generateLesson(780, 3);
    await vi.runAllTimersAsync();
    await expect(result).resolves.toEqual(lesson);
    expect(vi.mocked(request).mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });

  it('shows cancellation without issuing another generation', async () => {
    vi.mocked(request).mockResolvedValueOnce({ ...running, status: 'queued' })
      .mockResolvedValueOnce({ ...running, status: 'cancelled', error: 'Очередь остановлена' });
    const assertion = expect(generateLesson(780, 3)).rejects.toThrow('Очередь остановлена');
    await vi.runAllTimersAsync();
    await assertion;
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('surfaces a failed job without creating a second job', async () => {
    vi.mocked(request).mockResolvedValueOnce(running).mockResolvedValueOnce({ ...running, status: 'failed', error: 'Модель недоступна' });
    const assertion = expect(generateLesson(780, 3)).rejects.toThrow('Модель недоступна');
    await vi.runAllTimersAsync();
    await assertion;
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('does not retry start failures or terminal authentication failures', async () => {
    vi.mocked(request).mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(generateLesson(780, 3)).rejects.toThrow('Failed to fetch');
    expect(request).toHaveBeenCalledTimes(1);
    vi.mocked(request).mockReset().mockResolvedValueOnce(running).mockRejectedValueOnce(new ApiError(401, 'Сессия истекла'));
    const assertion = expect(generateLesson(780, 3)).rejects.toThrow('Сессия истекла');
    await vi.runAllTimersAsync();
    await assertion;
    expect(request).toHaveBeenCalledTimes(2);
  });
});
