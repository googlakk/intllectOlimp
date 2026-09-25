import type { Block, GeneratedLesson } from '@/lib/api/types';

/** Титульная страница урока: интригует до первого вопроса. */
export type LessonIntro = {
  kicker: string;
  title: string;
  accent?: string;
  hook: string;
  promise: string[];
  cta: string;
  imageUrl?: string;
  meta: string[];
};

const HOOK_LIMIT = 240;
const TITLE_LIMIT = 70;

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

/** «Что изучает физика? Научные исследования. (…)» → «Что изучает физика?» */
export function shortLessonTitle(topicName: string): string {
  const withoutBrackets = topicName.replace(/\s*\([^)]*\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
  const firstSentence = withoutBrackets.match(/^.+?[?!.](?=\s|$)/)?.[0] ?? withoutBrackets;
  if (firstSentence.length <= TITLE_LIMIT) return firstSentence.replace(/\.$/, '');
  const cut = firstSentence.slice(0, TITLE_LIMIT);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), 40)).trim()}…`;
}

/** Первые одна-две фразы первого абзаца, не длиннее лимита. */
export function hookFromText(source: string): string {
  const paragraph = source.split(/\n\s*\n/)[0].replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();
  if (paragraph.length <= HOOK_LIMIT) return paragraph;
  const sentences = paragraph.match(/[^.!?]+[.!?]+/g) ?? [paragraph];
  let hook = '';
  for (const sentence of sentences) {
    if ((hook + sentence).length > HOOK_LIMIT) break;
    hook += sentence;
  }
  return (hook || `${paragraph.slice(0, HOOK_LIMIT).trim()}…`).trim();
}

function firstImage(blocks: Block[]): string | undefined {
  for (const block of blocks) {
    const content = block.content as Record<string, unknown>;
    if (block.component === 'Presentation' && Array.isArray(content.slides)) {
      for (const slide of content.slides as Array<Record<string, unknown>>) {
        const media = slide?.media as Record<string, unknown> | undefined;
        if (media && media.kind !== 'video' && text(media.url)) return text(media.url);
      }
    }
    if (block.component === 'GeneratedMedia' && content.media_kind !== 'video') {
      const url = text(content.url) || text(content.data_url);
      if (url) return url;
    }
  }
  return undefined;
}

function firstSlideBody(blocks: Block[]): string {
  for (const block of blocks) {
    const slides = (block.content as Record<string, unknown>).slides;
    if (block.component === 'Presentation' && Array.isArray(slides)) {
      const body = text((slides[0] as Record<string, unknown> | undefined)?.body);
      if (body) return body;
    }
    if (block.component === 'ShortExplanation') {
      const body = text((block.content as Record<string, unknown>).text);
      if (body) return body;
    }
  }
  return '';
}

export function stepsLabel(count: number): string {
  const tail = count % 100;
  const last = count % 10;
  const word = tail >= 11 && tail <= 14 ? 'коротких шагов' : last === 1 ? 'короткий шаг' : last >= 2 && last <= 4 ? 'коротких шага' : 'коротких шагов';
  return `${count} ${word}`;
}

/**
 * Данные титула. Если генератор написал `lesson_metadata.intro`, берём его,
 * иначе собираем из уже имеющегося урока — так титул есть и у старых уроков.
 */
export function buildLessonIntro(lesson: GeneratedLesson | null | undefined): LessonIntro | null {
  const blocks = lesson?.blocks ?? [];
  if (!lesson || blocks.length === 0) return null;
  const metadata = lesson.lesson_metadata ?? {};
  const custom = (metadata.intro && typeof metadata.intro === 'object' ? metadata.intro : {}) as Record<string, unknown>;
  const contract = (metadata.topic_contract ?? {}) as Record<string, unknown>;

  const subject = text(contract.subject_name) || text(metadata.subject_name);
  const grade = Number(contract.grade || metadata.subject_grade);
  const kicker = text(custom.kicker) || [subject, grade > 0 ? `${grade} класс` : ''].filter(Boolean).join(' · ');
  const topicName = text(metadata.topic_name) || 'Урок';
  const objectives = Array.isArray(metadata.objectives)
    ? metadata.objectives.map((objective) => text(objective?.text)).filter(Boolean).slice(0, 3)
    : [];
  const fallbackPromise = text(metadata.learning_objectives);

  return {
    kicker,
    title: text(custom.title) || shortLessonTitle(topicName),
    accent: text(custom.accent) || undefined,
    hook: text(custom.hook) || hookFromText(firstSlideBody(blocks)) || fallbackPromise,
    promise: objectives.length ? objectives : (fallbackPromise ? [fallbackPromise] : []),
    cta: text(custom.cta) || 'Начать урок',
    imageUrl: text(custom.image_url) || firstImage(blocks),
    meta: [stepsLabel(blocks.length), 'В своём темпе', 'Без таймера'],
  };
}
