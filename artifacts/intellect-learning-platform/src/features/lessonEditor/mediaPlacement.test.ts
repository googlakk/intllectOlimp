import { describe, expect, it } from 'vitest';
import type { Block } from '@/lib/api/types';
import { placeGeneratedMedia, replaceGeneratedMediaJob } from './mediaPlacement';

const media = {
  kind: 'image' as const,
  url: 'https://cdn.example/diagram.png',
  alt_text: 'Схема делимости',
  caption: 'Учебная схема',
};

describe('AI media placement', () => {
  it('places media into the exact presentation slide without adding a block', () => {
    const blocks: Block[] = [{ component: 'Presentation', content: { title: 'Правила', slides: [
      { id: 'slide-1', heading: 'На 2', body: 'Первая мысль' },
      { id: 'slide-2', heading: 'На 3', body: 'Вторая мысль' },
    ] } }];
    const result = placeGeneratedMedia(blocks, {
      blockIndex: 0, slideIndex: 1, slideId: 'slide-2', mediaSlotId: 'media-slide-2',
      learningGoal: 'Понять признак делимости на 3', pedagogicalRole: 'clarify',
    }, media, 'Делимость');

    expect(result).toHaveLength(1);
    const slides = result[0].content.slides as Array<Record<string, unknown>>;
    expect(slides[0].media).toBeUndefined();
    expect((slides[1].media as Record<string, unknown>).url).toBe(media.url);
    expect((slides[1].media_slot as Record<string, unknown>).learning_purpose).toBe('Понять признак делимости на 3');
  });

  it('puts an image inside a concept or task block instead of a separate step', () => {
    const blocks: Block[] = [
      { component: 'ShortExplanation', content: { title: 'Идея' } },
      { component: 'GuidedPractice', content: { question: 'Попробуй', media_slot: { id: 'task-1', must_show: ['кубик'] } } },
    ];
    const result = placeGeneratedMedia(blocks, { blockIndex: 1, heading: 'Попробуй' }, media, 'Тема');

    expect(result.map((block) => block.component)).toEqual(['ShortExplanation', 'GuidedPractice']);
    expect((result[1].content.media as Record<string, unknown>).url).toBe(media.url);
    expect((result[1].content.media as Record<string, unknown>).media_slot_id).toBe('task-1');
    expect((result[1].content.media_slot as Record<string, unknown>).must_show).toEqual(['кубик']);
  });

  it('keeps videos and other components as a separate step after the block', () => {
    const blocks: Block[] = [
      { component: 'MindMap', content: { title: 'Идея' } },
      { component: 'GuidedPractice', content: { question: 'Попробуй' } },
    ];
    const result = placeGeneratedMedia(blocks, {
      blockIndex: 0, sceneId: 'scene-1', beatId: 'scene-1', heading: 'Идея',
    }, media, 'Тема');

    expect(result.map((block) => block.component)).toEqual(['MindMap', 'GeneratedMedia', 'GuidedPractice']);
    expect((result[1].content.anchor as Record<string, unknown>).scene_id).toBe('scene-1');
  });

  it('replaces a pending video by job id after polling completes', () => {
    const blocks: Block[] = [{ component: 'GeneratedMedia', content: {
      title: 'Процесс', media_kind: 'video', url: '', job_id: 'job-1',
    } }];
    const result = replaceGeneratedMediaJob(blocks, 'job-1', {
      kind: 'video', url: '/api/media/video/job-1/content', alt_text: 'Процесс', caption: 'Готово', job_id: 'job-1',
    });
    expect(result[0].content.url).toBe('/api/media/video/job-1/content');
  });
});
