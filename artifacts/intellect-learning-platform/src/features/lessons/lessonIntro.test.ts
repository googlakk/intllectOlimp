import { describe, expect, it } from 'vitest';
import type { GeneratedLesson } from '@/lib/api/types';
import { buildLessonIntro, hookFromText, shortLessonTitle, stepsLabel } from './lessonIntro';

const lesson = (patch: Partial<GeneratedLesson['lesson_metadata']> = {}, blocks: GeneratedLesson['blocks'] = []): GeneratedLesson => ({
  id: 1,
  topic_id: 1,
  blocks: blocks.length ? blocks : [
    { component: 'RetrievalCheck', content: { question: 'Что не вещество?' } },
    { component: 'Presentation', content: { title: 'T', slides: [
      { heading: 'Вопрос дня', body: 'Почему камень падает вниз? Физика изучает законы природы.\n\nВторой абзац.', media: { kind: 'image', url: 'https://x/img.png' } },
    ] } },
  ],
  lesson_metadata: {
    topic_name: 'Что изучает физика? Научные исследования. (материя, вещество, поле)',
    topic_contract: { subject_name: 'Физика', grade: 7 } as never,
    objectives: [{ id: 'o1', text: 'Различать вещество и поле' }] as never,
    ...patch,
  },
} as GeneratedLesson);

describe('lesson intro', () => {
  it('builds a title page for an existing lesson without generation', () => {
    const intro = buildLessonIntro(lesson());
    expect(intro).toMatchObject({
      kicker: 'Физика · 7 класс',
      title: 'Что изучает физика?',
      hook: 'Почему камень падает вниз? Физика изучает законы природы.',
      promise: ['Различать вещество и поле'],
      cta: 'Начать урок',
      imageUrl: 'https://x/img.png',
      meta: ['2 коротких шага', 'В своём темпе', 'Без таймера'],
    });
  });

  it('prefers the intro written by the generator', () => {
    const intro = buildLessonIntro(lesson({ intro: { title: 'Большая идея.', accent: 'Квадратный сад.', hook: 'Как превратить площадь в сторону?', cta: 'Спроектировать сад' } }));
    expect(intro?.title).toBe('Большая идея.');
    expect(intro?.accent).toBe('Квадратный сад.');
    expect(intro?.hook).toBe('Как превратить площадь в сторону?');
    expect(intro?.cta).toBe('Спроектировать сад');
  });

  it('finds an image in a generated media block and skips videos', () => {
    const intro = buildLessonIntro(lesson({}, [
      { component: 'GeneratedMedia', content: { media_kind: 'video', url: 'https://x/v.mp4' } },
      { component: 'GeneratedMedia', content: { media_kind: 'image', url: 'https://x/p.png' } },
    ]));
    expect(intro?.imageUrl).toBe('https://x/p.png');
  });

  it('returns nothing for an empty lesson', () => {
    expect(buildLessonIntro(null)).toBeNull();
    expect(buildLessonIntro({ ...lesson(), blocks: [] })).toBeNull();
  });

  it('shortens long titles and hooks', () => {
    expect(shortLessonTitle('Кубы и кубические корни')).toBe('Кубы и кубические корни');
    expect(shortLessonTitle('А'.repeat(90))).toMatch(/…$/);
    expect(hookFromText(`${'Первая фраза длинная. '.repeat(20)}`).length).toBeLessThanOrEqual(240);
  });

  it('declines the number of steps', () => {
    expect(stepsLabel(1)).toBe('1 короткий шаг');
    expect(stepsLabel(3)).toBe('3 коротких шага');
    expect(stepsLabel(12)).toBe('12 коротких шагов');
    expect(stepsLabel(22)).toBe('22 коротких шага');
  });
});
