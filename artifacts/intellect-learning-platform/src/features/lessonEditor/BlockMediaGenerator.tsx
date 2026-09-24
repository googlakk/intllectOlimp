import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ImageIcon, Loader2, PlayCircle, Sparkles, X } from 'lucide-react';
import {
  generateEducationalImage,
  generateEducationalVideo,
  getBlockMediaPlan,
  useUpdateLessonBlocks,
  type EducationalVideoResponse,
  type GeneratedLesson,
  type MediaRecommendation,
} from '@/lib/api';
import { lessonEditorInvalidationKeys } from './workflow';
import { placeGeneratedMedia, type MediaPlacementTarget, type PlacedLessonMedia } from './mediaPlacement';

export const MEDIA_CAPABLE_COMPONENTS = new Set([
  'ShortExplanation', 'KeyConcept', 'WorkedExample', 'MindMap', 'Timeline',
  'InteractiveGraph', 'Illustration', 'Presentation', 'PredictionLab',
  'DataInvestigation', 'PhysicsSandbox', 'HotspotInvestigation',
]);

export default function BlockMediaGenerator({ lesson, topicId, blockIndex, onClose }: {
  lesson: GeneratedLesson;
  topicId: number;
  blockIndex: number;
  onClose: () => void;
}) {
  const block = lesson.blocks[blockIndex];
  const slides = useMemo(() => block?.component === 'Presentation' && Array.isArray(block.content.slides)
    ? block.content.slides.filter((slide): slide is Record<string, unknown> => Boolean(slide) && typeof slide === 'object')
    : [], [block]);
  const [kind, setKind] = useState<'image' | 'video'>('image');
  const [slideIndex, setSlideIndex] = useState(0);
  const [teacherPrompt, setTeacherPrompt] = useState('');
  const queryClient = useQueryClient();
  const updateBlocks = useUpdateLessonBlocks();
  const planQuery = useQuery({
    queryKey: ['block-media-plan', lesson.id, lesson.active_version_id, blockIndex, slides.length ? slideIndex : null, kind],
    queryFn: () => getBlockMediaPlan({
      lesson_id: lesson.id,
      block_index: blockIndex,
      slide_index: slides.length ? slideIndex : undefined,
      preferred_kind: kind,
    }),
  });
  const recommendation = planQuery.data?.recommendations[0];

  const invalidate = async () => {
    await Promise.all(lessonEditorInvalidationKeys(topicId).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    queryClient.invalidateQueries({ queryKey: ['lesson-media-plan', lesson.id] });
  };

  const generation = useMutation({
    mutationFn: async (item: MediaRecommendation) => {
      const request = mediaRequest(lesson, item, teacherPrompt.trim());
      let media: PlacedLessonMedia;
      if (kind === 'image') {
        const result = await generateEducationalImage(request);
        media = {
          kind: 'image', url: result.url || result.data_url,
          alt_text: `Учебная визуализация: ${item.title}`,
          caption: item.learning_goal, prompt: result.prompt, model: result.model,
        };
      } else {
        const job = await generateEducationalVideo(request);
        media = videoMedia(job, item);
      }
      const nextBlocks = placeGeneratedMedia(lesson.blocks, recommendationTarget(item), media, planQuery.data?.topic || item.title);
      await updateBlocks.mutateAsync({ lesson_id: lesson.id, blocks: nextBlocks });
      await invalidate();
    },
    onSuccess: onClose,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="Создать AI-медиа для блока">
      <div className="w-full max-w-xl overflow-hidden rounded-t-lg border border-border bg-background shadow-2xl sm:rounded-lg">
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /><h3 className="truncate font-bold text-foreground">AI-медиа для блока</h3></div>
            <p className="mt-1 truncate text-xs text-muted-foreground">{blockTitle(block)}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Закрыть AI-генератор" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md hover:bg-muted"><X className="h-5 w-5" /></button>
        </div>

        <div className="space-y-4 p-5">
          {slides.length > 0 && (
            <label className="block text-xs font-semibold text-muted-foreground">
              Слайд, который нужно дополнить
              <select value={slideIndex} onChange={(event) => setSlideIndex(Number(event.target.value))} className="mt-1 h-10 w-full rounded-lg border border-border bg-card px-3 text-sm font-semibold text-foreground">
                {slides.map((slide, index) => <option key={String(slide.id || index)} value={index}>{index + 1}. {String(slide.heading || `Слайд ${index + 1}`)}</option>)}
              </select>
            </label>
          )}

          <div className="grid grid-cols-2 gap-2" aria-label="Формат медиа">
            <button type="button" onClick={() => setKind('image')} className={`flex h-11 items-center justify-center gap-2 rounded-lg border text-sm font-bold ${kind === 'image' ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground'}`}><ImageIcon className="h-4 w-4" /> Изображение</button>
            <button type="button" onClick={() => setKind('video')} className={`flex h-11 items-center justify-center gap-2 rounded-lg border text-sm font-bold ${kind === 'video' ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground'}`}><PlayCircle className="h-4 w-4" /> Видео</button>
          </div>

          <label className="block text-xs font-semibold text-muted-foreground">
            Что важно показать? <span className="font-normal">Необязательно</span>
            <textarea
              value={teacherPrompt}
              onChange={(event) => setTeacherPrompt(event.target.value)}
              placeholder="Например: покажи переход от квадрата к объёмному кубу и выдели третье измерение"
              className="mt-1 min-h-24 w-full resize-y rounded-lg border border-border bg-card px-3 py-2 text-sm font-normal text-foreground outline-none focus:border-primary"
            />
          </label>

          <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
            <p className="font-bold text-foreground">Системный визуальный контракт применяется автоматически</p>
            <p className="mt-1">Сохраняются стиль всего урока, точный контекст блока, учебная цель, терминология предмета и защита от фактических искажений. Ваше уточнение дополняет, но не заменяет эти правила.</p>
          </div>

          {planQuery.isLoading && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Анализируем выбранный блок...</div>}
          {recommendation && (
            <div className="text-xs text-muted-foreground"><span className="font-bold text-foreground">Будет встроено:</span> {recommendation.placement === 'slide_visual' ? `в слайд ${(recommendation.slide_index ?? 0) + 1}` : 'сразу после этого блока'} · {recommendation.learning_goal}</div>
          )}
          {(planQuery.error || generation.error || updateBlocks.error) && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{((planQuery.error || generation.error || updateBlocks.error) as Error).message}</div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-border p-4">
          <button type="button" onClick={onClose} className="h-10 rounded-lg border border-border px-4 text-sm font-bold hover:bg-muted">Отмена</button>
          <button
            type="button"
            onClick={() => recommendation && generation.mutate(recommendation)}
            disabled={!recommendation || generation.isPending || updateBlocks.isPending}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {generation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {generation.isPending ? 'Создаём...' : `Создать ${kind === 'image' ? 'изображение' : 'видео'}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function recommendationTarget(item: MediaRecommendation): MediaPlacementTarget {
  return {
    blockIndex: item.block_index, slideIndex: item.slide_index ?? undefined,
    sceneId: item.scene_id, beatId: item.beat_id, slideId: item.slide_id,
    mediaSlotId: item.slide_id ? `media-${item.slide_id}` : undefined,
    heading: item.heading, learningGoal: item.learning_goal,
    pedagogicalRole: item.pedagogical_role, visualIntent: item.visual_intent,
    successCheck: item.success_check, requiredVisuals: item.must_include, avoidedVisuals: item.avoid,
  };
}

function mediaRequest(lesson: GeneratedLesson, item: MediaRecommendation, teacherPrompt: string) {
  const metadata = lesson.lesson_metadata || {};
  return {
    lesson_version_id: lesson.active_version_id || undefined,
    scene_id: item.scene_id, block_id: `block-${item.block_index + 1}`,
    beat_id: item.beat_id, slide_id: item.slide_id,
    media_slot_id: item.slide_id ? `media-${item.slide_id}` : undefined,
    placement: item.placement,
    topic: String(metadata.topic_name || item.title),
    subject: typeof metadata.subject_name === 'string' ? metadata.subject_name : undefined,
    grade: typeof metadata.subject_grade === 'number' ? metadata.subject_grade : undefined,
    concept: item.heading, learning_goal: item.learning_goal,
    source_context: item.source_context, curriculum_context: curriculumSummary(lesson),
    visual_form: item.visual_form, visual_intent: item.visual_intent,
    pedagogical_role: item.pedagogical_role, must_include: item.must_include,
    avoid: item.avoid, success_check: item.success_check, style: item.style,
    prompt: teacherPrompt || undefined, labels_language: 'ru', aspect_ratio: '16:9',
    resolution: item.kind === 'image' ? '1K' : '720p',
    ...(item.kind === 'image' ? { quality: 'medium' } : { duration: 6, generate_audio: false }),
  };
}

function videoMedia(job: EducationalVideoResponse, item: MediaRecommendation): PlacedLessonMedia {
  return {
    kind: 'video', url: job.content_url || '', alt_text: `Учебное видео: ${item.title}`,
    caption: item.learning_goal, job_id: job.id, generation_id: job.generation_id,
    prompt: job.prompt, model: job.model,
  };
}

function curriculumSummary(lesson: GeneratedLesson): string {
  const metadata = lesson.lesson_metadata || {};
  const objectives = Array.isArray(metadata.objectives)
    ? metadata.objectives.map((item) => item && typeof item === 'object' ? String((item as { text?: unknown }).text || '') : '').filter(Boolean)
    : [];
  return [String(metadata.learning_focus || ''), ...objectives].filter(Boolean).join('; ').slice(0, 1200);
}

function blockTitle(block: GeneratedLesson['blocks'][number] | undefined): string {
  if (!block) return 'Учебный блок';
  for (const key of ['title', 'heading', 'term', 'question', 'problem', 'prompt', 'task']) {
    if (typeof block.content[key] === 'string' && block.content[key]) return String(block.content[key]);
  }
  return block.component;
}
