import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ImageIcon, Loader2 } from 'lucide-react';
import { generateEducationalImage, getLessonMediaPlan, updateLessonBlocks, type AiModelGroup, type GeneratedLesson } from '@/lib/api';
import ModelPicker, { type ModelChoice } from './ModelPicker';
import { runLessonIllustrations, type IllustrationProgress } from './lessonIllustrations';
import { lessonEditorInvalidationKeys } from './workflow';

const AUTO_KEY = 'intellect:auto-illustrations';
// Ориентир по цене — только для модели по умолчанию, у остальных цена заметно выше.
const PRICE_HINT: Record<string, string> = { 'openrouter:google/gemini-2.5-flash-image': '≈ $0.04 за картинку' };

function readAuto(): boolean {
  try { return window.localStorage.getItem(AUTO_KEY) !== 'false'; } catch { return true; }
}

const planKey = (lesson?: GeneratedLesson | null) => ['lesson-illustration-plan', lesson?.id, lesson?.active_version_id];

/** Автоиллюстрации урока: запуск после генерации и дозаполнение пустых мест. */
export function useLessonIllustrations(topicId: number, imageModel: string | undefined) {
  const client = useQueryClient();
  const [enabled, setEnabledState] = useState(readAuto);
  const [progress, setProgress] = useState<IllustrationProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const setEnabled = (value: boolean) => {
    setEnabledState(value);
    try { window.localStorage.setItem(AUTO_KEY, String(value)); } catch { /* только удобство */ }
  };

  const start = async (lesson: GeneratedLesson) => {
    if (running) return;
    setRunning(true);
    setError('');
    setProgress(null);
    try {
      const plan = await getLessonMediaPlan(lesson.id, { imagesOnly: true });
      await runLessonIllustrations({
        lesson,
        items: plan.recommendations,
        model: imageModel,
        generateImage: generateEducationalImage,
        saveBlocks: (blocks) => updateLessonBlocks(lesson.id, blocks),
        onProgress: setProgress,
      });
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setRunning(false);
      await Promise.all([...lessonEditorInvalidationKeys(topicId), ['lesson-illustration-plan']].map((queryKey) => client.invalidateQueries({ queryKey })));
    }
  };

  return { enabled, setEnabled, start, running, progress, error };
}

export type LessonIllustrationsState = ReturnType<typeof useLessonIllustrations>;

export function LessonIllustrationsPanel({ lesson, state, imageGroup, imageChoice, disabled }: {
  lesson?: GeneratedLesson | null;
  state: LessonIllustrationsState;
  imageGroup?: AiModelGroup;
  imageChoice: ModelChoice;
  disabled?: boolean;
}) {
  const plan = useQuery({
    queryKey: planKey(lesson),
    queryFn: () => getLessonMediaPlan(lesson!.id, { imagesOnly: true }),
    enabled: Boolean(lesson?.id && lesson.blocks?.length) && !state.running,
    staleTime: 30_000,
  });
  const missing = plan.data?.recommendations.filter((item) => item.kind === 'image').length ?? 0;
  const limit = plan.data?.limit;
  const price = PRICE_HINT[imageChoice.value];
  const { progress } = state;

  return (
    <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4">
      <label className="flex items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 h-4 w-4" checked={state.enabled} disabled={disabled || state.running} onChange={(event) => state.setEnabled(event.target.checked)} />
        <span>
          <span className="font-semibold">Сразу с иллюстрациями</span>
          <span className="block text-muted-foreground">
            После черновика ИИ нарисует картинки к слайдам, понятиям и сценам задач: {limit ? `до ${limit}` : 'от 3 до 8 в зависимости от объёма урока'}{price ? `, ${price}` : ''}. Ответы на картинках не показываются.
          </span>
        </span>
      </label>
      <div className="mt-3 max-w-md"><ModelPicker label="Модель для иллюстраций" group={imageGroup} choice={imageChoice} disabled={disabled || state.running} /></div>

      {state.running && (
        <p role="status" className="mt-3 flex items-center gap-2 text-sm font-semibold text-primary">
          <Loader2 className="h-4 w-4 animate-spin" />
          {progress ? `Иллюстрации: ${progress.done + progress.failed.length} из ${progress.total}` : 'Выбираем места для иллюстраций…'} · не редактируйте блоки, пока идёт генерация
        </p>
      )}
      {!state.running && progress && (
        <p role="status" className="mt-3 text-sm">
          Готово иллюстраций: {progress.done} из {progress.total}.
        </p>
      )}
      {(state.error || (progress && progress.failed.length > 0)) && !state.running && (
        <div role="alert" className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {state.error || <>Не получилось: <ul className="ml-5 list-disc">{progress!.failed.map((item) => <li key={item}>{item}</li>)}</ul></>}
        </div>
      )}
      {!state.running && lesson && missing > 0 && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => void state.start(lesson)}
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-primary px-4 py-2 text-sm font-bold text-primary disabled:opacity-50"
        >
          <ImageIcon className="h-4 w-4" /> Догенерировать недостающие ({missing})
        </button>
      )}
    </div>
  );
}
