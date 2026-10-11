import { ApiError, request } from './client';
import type { GeneratedLesson } from './types';
import type { InstructionLanguage } from '@/lib/languages';

export type LessonGenerationStatus = {
  job_id: string;
  topic_id: number;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  error?: string | null;
  lesson?: GeneratedLesson | null;
};

const POLL_INTERVAL_MS = 2500;
const MAX_WAIT_MS = 16 * 60 * 1000;
const MAX_READ_FAILURES = 5;

const pause = () => new Promise<void>(resolve => setTimeout(resolve, POLL_INTERVAL_MS));

// Only status reads are retried: a connection failure must never create another paid job.
export async function generateLesson(
  topicId: number,
  teacherId: number,
  model?: string,
  contentLanguage?: InstructionLanguage,
): Promise<GeneratedLesson> {
  let job = await request<LessonGenerationStatus>('/lessons/generate/start', {
    method: 'POST',
    body: JSON.stringify({
      topic_id: topicId,
      teacher_id: teacherId,
      request_id: crypto.randomUUID(),
      ...(model ? { model } : {}),
      ...(contentLanguage ? { content_language: contentLanguage } : {}),
    }),
  });
  const deadline = Date.now() + MAX_WAIT_MS;
  let readFailures = 0;
  while (job.status === 'queued' || job.status === 'running') {
    if (Date.now() >= deadline) {
      throw new Error('Не удалось дождаться результата. Откройте урок позже, чтобы проверить готовый черновик.');
    }
    await pause();
    try {
      job = await request<LessonGenerationStatus>(`/lessons/generate/status/${encodeURIComponent(job.job_id)}?topic_id=${topicId}`);
      readFailures = 0;
    } catch (error) {
      const transient = error instanceof TypeError || (error instanceof ApiError && error.status >= 500);
      if (!transient || ++readFailures >= MAX_READ_FAILURES) throw error;
    }
  }
  if (job.status === 'failed' || job.status === 'cancelled') throw new Error(job.error || 'Не удалось подготовить урок. Попробуйте ещё раз.');
  if (!job.lesson) throw new Error('Сервер не вернул подготовленный урок. Откройте урок повторно.');
  return job.lesson;
}
