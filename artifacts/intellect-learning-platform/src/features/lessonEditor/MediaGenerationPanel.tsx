import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ImageIcon, Loader2, PlayCircle, Sparkles, WandSparkles } from 'lucide-react';
import {
  generateEducationalImage,
  generateEducationalVideo,
  getEducationalVideoStatus,
  getLessonMediaPlan,
  useUpdateLessonBlocks,
  type Block,
  type EducationalVideoResponse,
  type GeneratedLesson,
  type MediaRecommendation,
} from '@/lib/api';
import { lessonEditorInvalidationKeys } from './workflow';
import {
  placeGeneratedMedia,
  replaceGeneratedMediaJob,
  type MediaPlacementTarget as MediaTarget,
  type PlacedLessonMedia as PlacedMedia,
} from './mediaPlacement';

type MediaGenerationPanelProps = {
  topicId: number;
  lesson: GeneratedLesson;
};

type PendingVideo = { job: EducationalVideoResponse; recommendation: MediaRecommendation };

export default function MediaGenerationPanel({ topicId, lesson }: MediaGenerationPanelProps) {
  const queryClient = useQueryClient();
  const updateBlocksMutation = useUpdateLessonBlocks();
  const workingBlocks = useRef<Block[]>(lesson.blocks || []);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [pendingVideos, setPendingVideos] = useState<PendingVideo[]>([]);
  const [itemStatus, setItemStatus] = useState<Record<string, 'idle' | 'generating' | 'ready' | 'error'>>({});
  const [mediaError, setMediaError] = useState('');

  useEffect(() => { workingBlocks.current = lesson.blocks || []; }, [lesson.blocks]);

  const planQuery = useQuery({
    queryKey: ['lesson-media-plan', lesson.id, lesson.active_version_id, lesson.blocks],
    queryFn: () => getLessonMediaPlan(lesson.id),
    staleTime: 30_000,
  });
  const recommendations = useMemo(() => planQuery.data?.recommendations || [], [planQuery.data]);

  useEffect(() => {
    const availableIds = recommendations.map((item) => item.id);
    setSelectedIds((current) => {
      const retained = current.filter((id) => availableIds.includes(id));
      return retained.length > 0 ? retained : availableIds;
    });
  }, [recommendations]);

  const invalidate = async () => {
    await Promise.all(lessonEditorInvalidationKeys(topicId).map((queryKey) => (
      queryClient.invalidateQueries({ queryKey })
    )));
  };

  const generationMutation = useMutation({
    mutationFn: async (items: MediaRecommendation[]) => {
      setMediaError('');
      let nextBlocks = workingBlocks.current;
      const nextPending: PendingVideo[] = [];
      const failures: string[] = [];
      const ordered = [...items].sort((a, b) => b.block_index - a.block_index || (b.slide_index ?? -1) - (a.slide_index ?? -1));
      for (const recommendation of ordered) {
        setItemStatus((current) => ({ ...current, [recommendation.id]: 'generating' }));
        try {
          const target = recommendationTarget(recommendation);
          if (recommendation.kind === 'image') {
            const result = await generateEducationalImage(mediaRequest(lesson, recommendation));
            nextBlocks = placeGeneratedMedia(nextBlocks, target, {
              kind: 'image',
              url: result.url || result.data_url,
              alt_text: `Учебная визуализация: ${recommendation.title}`,
              caption: recommendation.learning_goal,
              prompt: result.prompt,
              model: result.model,
            }, planQuery.data?.topic || recommendation.title);
            setItemStatus((current) => ({ ...current, [recommendation.id]: 'ready' }));
          } else {
            const job = await generateEducationalVideo(mediaRequest(lesson, recommendation));
            nextBlocks = placeGeneratedMedia(nextBlocks, target, videoMedia(job, recommendation), planQuery.data?.topic || recommendation.title);
            if (!job.content_url) nextPending.push({ job, recommendation });
            setItemStatus((current) => ({ ...current, [recommendation.id]: job.content_url ? 'ready' : 'generating' }));
          }
        } catch (error) {
          setItemStatus((current) => ({ ...current, [recommendation.id]: 'error' }));
          failures.push(`${recommendation.title}: ${(error as Error).message}`);
        }
      }
      workingBlocks.current = nextBlocks;
      if (nextBlocks !== lesson.blocks) {
        await updateBlocksMutation.mutateAsync({ lesson_id: lesson.id, blocks: nextBlocks });
      }
      setPendingVideos((current) => [...current, ...nextPending]);
      await invalidate();
      if (failures.length > 0) throw new Error(failures.join('\n'));
    },
    onError: (error) => setMediaError((error as Error).message),
  });

  useEffect(() => {
    if (pendingVideos.length === 0) return;
    const timer = window.setTimeout(async () => {
      const remaining: PendingVideo[] = [];
      let changed = false;
      for (const pending of pendingVideos) {
        try {
          const job = await getEducationalVideoStatus(pending.job.id);
          if (job.content_url) {
            workingBlocks.current = replaceGeneratedMediaJob(
              workingBlocks.current,
              pending.job.id,
              videoMedia(job, pending.recommendation),
            );
            setItemStatus((current) => ({ ...current, [pending.recommendation.id]: 'ready' }));
            changed = true;
          } else if (['failed', 'cancelled'].includes(job.status)) {
            setItemStatus((current) => ({ ...current, [pending.recommendation.id]: 'error' }));
          } else {
            remaining.push({ job, recommendation: pending.recommendation });
          }
        } catch {
          remaining.push(pending);
        }
      }
      setPendingVideos(remaining);
      if (changed) {
        await updateBlocksMutation.mutateAsync({ lesson_id: lesson.id, blocks: workingBlocks.current });
        await invalidate();
      }
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [pendingVideos, lesson.id]);

  const selected = recommendations.filter((item) => selectedIds.includes(item.id));
  const busy = generationMutation.isPending || updateBlocksMutation.isPending;

  return (
    <section className="mb-8 border-y border-border bg-muted/20 py-5" data-testid="context-media-planner">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <WandSparkles className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Контент внутри объяснения</h2>
          </div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Система сама выбрала формат и место по смыслу урока. Для предмета «{planQuery.data?.subject || 'текущий предмет'}» используется профиль {familyLabel(planQuery.data?.subject_family)}.
          </p>
        </div>
        <button
          type="button"
          onClick={() => generationMutation.mutate(selected)}
          disabled={busy || selected.length === 0}
          className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-bold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {busy ? 'Создаём и встраиваем...' : `Создать материалы (${selected.length})`}
        </button>
      </div>

      {planQuery.isLoading ? (
        <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Анализируем структуру урока...</div>
      ) : recommendations.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
          Все подходящие точки уже заполнены или этому уроку не требуется дополнительное медиа.
        </p>
      ) : (
        <div className="mt-4 grid gap-2 lg:grid-cols-2">
          {recommendations.map((item) => {
            const active = selectedIds.includes(item.id);
            const status = itemStatus[item.id] || 'idle';
            return (
              <button
                type="button"
                key={item.id}
                onClick={() => setSelectedIds((current) => active ? current.filter((id) => id !== item.id) : [...current, item.id])}
                className={`flex min-h-24 items-start gap-3 rounded-lg border p-3 text-left transition-colors ${active ? 'border-primary bg-primary/5' : 'border-border bg-background hover:border-primary/40'}`}
              >
                <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                  {status === 'generating' ? <Loader2 className="h-4 w-4 animate-spin" /> : status === 'ready' ? <Check className="h-4 w-4" /> : item.kind === 'image' ? <ImageIcon className="h-4 w-4" /> : <PlayCircle className="h-4 w-4" />}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-bold text-foreground">{item.title}</span>
                  <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">{item.reason}</span>
                  <span className="mt-2 block text-[11px] font-semibold uppercase text-primary">{item.kind === 'image' ? 'Изображение' : 'Короткое видео'} · {item.placement === 'slide_visual' ? `слайд ${(item.slide_index ?? 0) + 1}` : `после блока ${item.block_index + 1}`}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {(mediaError || planQuery.error || updateBlocksMutation.error) && (
        <div role="alert" className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm font-medium text-destructive">
          {mediaError || (planQuery.error as Error)?.message || (updateBlocksMutation.error as Error)?.message}
        </div>
      )}
    </section>
  );
}

function recommendationTarget(item: MediaRecommendation): MediaTarget {
  return {
    blockIndex: item.block_index,
    slideIndex: item.slide_index ?? undefined,
    sceneId: item.scene_id,
    beatId: item.beat_id,
    slideId: item.slide_id,
    mediaSlotId: item.slide_id ? `media-${item.slide_id}` : undefined,
    heading: item.heading,
    learningGoal: item.learning_goal,
    pedagogicalRole: item.pedagogical_role,
    visualIntent: item.visual_intent,
    successCheck: item.success_check,
    requiredVisuals: item.must_include,
    avoidedVisuals: item.avoid,
  };
}

function mediaRequest(lesson: GeneratedLesson, item: MediaRecommendation) {
  const metadata = lesson.lesson_metadata || {};
  return {
    lesson_version_id: lesson.active_version_id || undefined,
    scene_id: item.scene_id,
    block_id: `block-${item.block_index + 1}`,
    beat_id: item.beat_id,
    slide_id: item.slide_id,
    media_slot_id: item.slide_id ? `media-${item.slide_id}` : undefined,
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
    resolution: item.kind === 'image' ? '1K' : '720p',
    ...(item.kind === 'image' ? { quality: 'medium' } : { duration: 6, generate_audio: false }),
  };
}

function videoMedia(job: EducationalVideoResponse, item: MediaRecommendation): PlacedMedia {
  return {
    kind: 'video',
    url: job.content_url || '',
    alt_text: `Учебное видео: ${item.title}`,
    caption: item.learning_goal,
    job_id: job.id,
    generation_id: job.generation_id,
    prompt: job.prompt,
    model: job.model,
  };
}

function curriculumSummary(lesson: GeneratedLesson): string {
  const metadata = lesson.lesson_metadata || {};
  const objectives = Array.isArray(metadata.objectives)
    ? metadata.objectives.map((item) => item && typeof item === 'object' ? String((item as { text?: unknown }).text || '') : '').filter(Boolean)
    : [];
  return [String(metadata.learning_focus || ''), ...objectives].filter(Boolean).join('; ').slice(0, 1200);
}

function familyLabel(value?: string): string {
  return ({
    humanities: 'литературы и языков', social_science: 'общественных наук', natural_science: 'естественных наук',
    physics: 'физики', geography: 'географии', computing: 'информатики', mathematics: 'математики', general: 'общего курса',
  } as Record<string, string>)[value || 'general'] || 'текущего предмета';
}
