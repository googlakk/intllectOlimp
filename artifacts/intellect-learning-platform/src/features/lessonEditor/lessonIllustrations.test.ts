import { describe, expect, it, vi } from 'vitest';
import type { Block, GeneratedLesson, MediaRecommendation } from '@/lib/api/types';
import { illustrationRequest, runLessonIllustrations } from './lessonIllustrations';

const lesson = (blocks: Block[]): GeneratedLesson => ({
  id: 7, topic_id: 3, blocks, active_version_id: 11,
  lesson_metadata: { topic_name: 'Плотность', subject_name: 'Физика', subject_grade: 7 },
} as unknown as GeneratedLesson);

const rec = (patch: Partial<MediaRecommendation>): MediaRecommendation => ({
  id: 'r', kind: 'image', title: 'Сцена', reason: '', subject_family: 'science', block_index: 0,
  heading: 'Сцена', learning_goal: 'Понять', source_context: '', visual_intent: 'x', visual_form: 'scene',
  pedagogical_role: 'clarify', style: 's', must_include: [], avoid: [], success_check: '',
  placement: 'block_visual', component: 'KeyConcept', priority: 1, ...patch,
} as MediaRecommendation);

describe('lesson illustrations', () => {
  it('builds an image request with the chosen model and the slot id', () => {
    const request = illustrationRequest(lesson([]), rec({ media_slot_id: 'kc' }), 'openrouter:google/gemini-2.5-flash-image');
    expect(request).toMatchObject({ lesson_version_id: 11, media_slot_id: 'kc', subject: 'Физика', grade: 7, model: 'openrouter:google/gemini-2.5-flash-image' });
  });

  it('places every image into its block and saves after each one', async () => {
    const blocks: Block[] = [
      { component: 'KeyConcept', content: { term: 'Плотность' } },
      { component: 'Presentation', content: { slides: [{ id: 's1', heading: 'A', body: 'B' }] } },
    ];
    const saves: Block[][] = [];
    const saveBlocks = vi.fn(async (next: Block[]) => { saves.push(next); return lesson(next); });
    const generateImage = vi.fn(async () => ({ url: 'https://img/x.png', prompt: 'p', model: 'm' }) as never);
    const progress = await runLessonIllustrations({
      lesson: lesson(blocks),
      items: [rec({ id: 'a', block_index: 0 }), rec({ id: 'b', block_index: 1, slide_index: 0, slide_id: 's1', placement: 'slide_visual', component: 'Presentation' })],
      generateImage,
      saveBlocks,
    });
    expect(progress).toEqual({ total: 2, done: 2, failed: [] });
    expect(saveBlocks).toHaveBeenCalledTimes(2);
    const last = saves.at(-1)!;
    expect((last[0].content.media as Record<string, unknown>).url).toBe('https://img/x.png');
    expect(((last[1].content.slides as Array<Record<string, unknown>>)[0].media as Record<string, unknown>).url).toBe('https://img/x.png');
  });

  it('skips videos and reports failures without stopping the rest', async () => {
    const blocks: Block[] = [{ component: 'KeyConcept', content: {} }, { component: 'ShortExplanation', content: {} }];
    const generateImage = vi.fn()
      .mockRejectedValueOnce(new Error('лимит'))
      .mockResolvedValueOnce({ url: 'https://img/ok.png' });
    const progress = await runLessonIllustrations({
      lesson: lesson(blocks),
      items: [rec({ id: 'a', title: 'Первая' }), rec({ id: 'v', kind: 'video' }), rec({ id: 'b', block_index: 1, title: 'Вторая', component: 'ShortExplanation' })],
      generateImage,
      saveBlocks: async (next) => lesson(next),
    });
    expect(generateImage).toHaveBeenCalledTimes(2);
    expect(progress.total).toBe(2);
    expect(progress.done).toBe(1);
    expect(progress.failed).toEqual(['Первая: лимит']);
  });
});
