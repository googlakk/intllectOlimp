import type { Block, EducationalImageResponse, GeneratedLesson, MediaRecommendation } from '@/lib/api/types';
import { placeGeneratedMedia, type MediaPlacementTarget } from './mediaPlacement';

/** Сколько картинок создаём одновременно: быстрее, но без лавины запросов. */
export const ILLUSTRATION_CONCURRENCY = 2;

export type IllustrationProgress = { total: number; done: number; failed: string[] };

export function illustrationTarget(item: MediaRecommendation): MediaPlacementTarget {
  return {
    blockIndex: item.block_index,
    slideIndex: item.slide_index ?? undefined,
    sceneId: item.scene_id,
    beatId: item.beat_id,
    slideId: item.slide_id,
    mediaSlotId: item.media_slot_id || (item.slide_id ? `media-${item.slide_id}` : undefined),
    heading: item.heading,
    learningGoal: item.learning_goal,
    pedagogicalRole: item.pedagogical_role,
    visualIntent: item.visual_intent,
    successCheck: item.success_check,
    requiredVisuals: item.must_include,
    avoidedVisuals: item.avoid,
  };
}

function curriculumSummary(lesson: GeneratedLesson): string {
  const metadata = lesson.lesson_metadata || {};
  const objectives = Array.isArray(metadata.objectives)
    ? metadata.objectives.map((item) => (item && typeof item === 'object' ? String((item as { text?: unknown }).text || '') : '')).filter(Boolean)
    : [];
  return [String(metadata.learning_focus || ''), ...objectives].filter(Boolean).join('; ').slice(0, 1200);
}

export function illustrationRequest(lesson: GeneratedLesson, item: MediaRecommendation, model?: string) {
  const metadata = lesson.lesson_metadata || {};
  return {
    lesson_version_id: lesson.active_version_id || undefined,
    scene_id: item.scene_id,
    block_id: `block-${item.block_index + 1}`,
    beat_id: item.beat_id,
    slide_id: item.slide_id,
    media_slot_id: illustrationTarget(item).mediaSlotId,
    placement: item.placement,
    topic: String(metadata.topic_name || item.title),
    subject: typeof metadata.subject_name === 'string' ? metadata.subject_name : undefined,
    grade: typeof metadata.subject_grade === 'number' ? metadata.subject_grade : undefined,
    concept: item.heading,
    learning_goal: item.learning_goal,
    source_context: item.source_context,
    curriculum_context: curriculumSummary(lesson),
    visual_form: item.visual_form,
    visual_intent: item.visual_intent,
    pedagogical_role: item.pedagogical_role,
    must_include: item.must_include,
    avoid: item.avoid,
    success_check: item.success_check,
    style: item.style,
    labels_language: 'ru',
    aspect_ratio: '16:9',
    resolution: '1K',
    quality: 'medium',
    ...(model ? { model } : {}),
  };
}

type RunOptions = {
  lesson: GeneratedLesson;
  items: MediaRecommendation[];
  model?: string;
  generateImage: (request: ReturnType<typeof illustrationRequest>) => Promise<EducationalImageResponse>;
  saveBlocks: (blocks: Block[]) => Promise<GeneratedLesson>;
  onProgress?: (progress: IllustrationProgress) => void;
};

/**
 * Создаёт картинки по плану и встраивает их в урок. Каждая готовая картинка
 * сразу сохраняется: если учитель закроет страницу, оплаченное не пропадёт,
 * а «Догенерировать недостающие» возьмёт только пустые места.
 */
export async function runLessonIllustrations({ lesson, items, model, generateImage, saveBlocks, onProgress }: RunOptions): Promise<IllustrationProgress> {
  const images = items.filter((item) => item.kind === 'image');
  const progress: IllustrationProgress = { total: images.length, done: 0, failed: [] };
  const topic = String(lesson.lesson_metadata?.topic_name || 'Урок');
  let current = lesson;
  let saving: Promise<unknown> = Promise.resolve();
  onProgress?.({ ...progress });

  const place = (item: MediaRecommendation, result: EducationalImageResponse) => {
    // Сохранения идут строго по очереди, каждое поверх предыдущего.
    saving = saving.then(async () => {
      const blocks = placeGeneratedMedia(current.blocks || [], illustrationTarget(item), {
        kind: 'image',
        url: result.url || result.data_url || '',
        alt_text: `Иллюстрация: ${item.title}`,
        caption: '',
        prompt: result.prompt,
        model: result.model,
      }, topic);
      current = { ...current, ...(await saveBlocks(blocks)) };
    });
    return saving;
  };

  let next = 0;
  const worker = async () => {
    while (next < images.length) {
      const item = images[next++];
      try {
        const result = await generateImage(illustrationRequest(current, item, model));
        if (!result.url && !result.data_url) throw new Error('модель не вернула изображение');
        await place(item, result);
        progress.done += 1;
      } catch (error) {
        progress.failed.push(`${item.title}: ${(error as Error).message}`);
      }
      onProgress?.({ ...progress, failed: [...progress.failed] });
    }
  };
  await Promise.all(Array.from({ length: Math.min(ILLUSTRATION_CONCURRENCY, images.length) }, worker));
  await saving;
  return progress;
}
