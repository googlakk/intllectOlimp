import { BookMarked, ChevronDown, RefreshCw } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import type React from 'react';
import { componentMap, preloadBlockComponent } from '@/components/blocks/BlockRenderer';
import { BlockMedia } from '@/components/blocks/BlockMedia';
import type { Block, LessonDocument } from '@/lib/api/types';
import { tutorAttemptProps } from '@/features/tutor/tutorBridge';
import { useTutorBridge } from '@/features/tutor/TutorBridgeContext';
import { TutorDock } from '@/features/tutor/TutorDock';
import type { LessonTutor } from '@/features/tutor/useLessonTutor';
import { isAssessmentBlock, type AttemptsByStep, type LessonAnswers } from './studentProgress';
import { avatarCueForBeat, lessonPositionForBlock } from './lessonExperience';
import { narrationSpeechText } from './lessonContent';

const PHASE_LABELS: Record<string, string> = {
  ShortExplanation: 'Объяснение',
  KeyConcept: 'Ключевое понятие',
  WorkedExample: 'Разобранный пример',
  GuidedPractice: 'Практика с поддержкой',
  IndependentProblem: 'Самостоятельная практика',
  RetrievalCheck: 'Проверка понимания',
  TextEvidencePicker: 'Работа с текстом',
  ArgumentBuilder: 'Аргументация',
  MasteryCheck: 'Итоговая проверка',
  Reflection: 'Рефлексия',
  MindMap: 'Связи между идеями',
  Timeline: 'Последовательность событий',
  InteractiveGraph: 'Исследование данных',
  Presentation: 'Материал урока',
  Illustration: 'Визуальная модель',
  SortAndClassify: 'Классификация',
  ProcessBuilder: 'Сборка процесса',
  ArgumentMap: 'Карта аргумента',
  BranchingScenario: 'Сценарий выбора',
  MisconceptionDebugger: 'Разбор ошибки',
  PredictionLab: 'Прогноз и наблюдение',
  DataInvestigation: 'Исследование данных',
  PhysicsSandbox: 'Физическая модель',
  HotspotInvestigation: 'Исследование схемы',
  CodeBlocksLab: 'Алгоритм из блоков',
  ChronologyLine: 'Лента событий',
  CauseEffectMap: 'Причины и следствия',
};

type ActiveLessonContentProps = {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  contentRef: React.RefObject<HTMLDivElement | null>;
  currentStep: number;
  isCompleted: boolean;
  isDiagnosticRoute: boolean;
  lessonDocument?: LessonDocument;
  lessonVersionId?: number | null;
  activeBeatId?: string;
  onTeachingBeatChange: (beatId: string) => void;
  maxOpenedStep: number;
  prefersReducedMotion: boolean | null;
  retryKeys: Record<number, number>;
  onAnswer: (blockIndex: number, isCorrect: boolean) => void;
  onNavigate: (index: number) => void;
  onNext: () => void;
  onOpenSummary: () => void;
  onSaveIntermediate: (answers: LessonAnswers, attempts: AttemptsByStep) => void;
  onSetAnswers: (answers: LessonAnswers) => void;
  onSetRetryKeys: React.Dispatch<React.SetStateAction<Record<number, number>>>;
  avatarEnabled: boolean;
  audioEnabled: boolean;
  onAvatarEnabledChange: (enabled: boolean) => void;
  onAudioEnabledChange: (enabled: boolean) => void;
  /** Помощник урока — только когда он включён для ученика. */
  tutor?: LessonTutor;
};

export function ActiveLessonContent({
  activeBlocks,
  activeOriginalIndices,
  answers,
  attemptsByStep,
  contentRef,
  currentStep,
  isCompleted,
  isDiagnosticRoute,
  lessonDocument,
  lessonVersionId,
  activeBeatId,
  onTeachingBeatChange,
  maxOpenedStep,
  prefersReducedMotion,
  retryKeys,
  onAnswer,
  onNavigate,
  onNext,
  onOpenSummary,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
  avatarEnabled,
  audioEnabled,
  onAvatarEnabledChange,
  onAudioEnabledChange,
  tutor,
}: ActiveLessonContentProps) {
  const block = activeBlocks[currentStep];
  const phaseLabel = block?.content?.evidence_stage === 'diagnostic'
    ? 'Разминка'
    : PHASE_LABELS[block?.component] || 'Учебный шаг';
  const originalIndex = activeOriginalIndices[currentStep] ?? currentStep;
  const blockIsAssessment = block ? isAssessmentBlock(block) : false;
  const position = lessonPositionForBlock(lessonDocument, originalIndex);
  const cue = avatarCueForBeat(position?.scene, activeBeatId);

  useEffect(() => {
    preloadBlockComponent(activeBlocks[currentStep]?.component);
    const preloadNext = () => {
      preloadBlockComponent(activeBlocks[currentStep + 1]?.component);
    };
    const idleCallback = window.requestIdleCallback?.(preloadNext, { timeout: 900 });
    const fallbackTimer = idleCallback === undefined
      ? window.setTimeout(preloadNext, 160)
      : undefined;
    return () => {
      if (idleCallback !== undefined) window.cancelIdleCallback?.(idleCallback);
      if (fallbackTimer !== undefined) window.clearTimeout(fallbackTimer);
    };
  }, [activeBlocks, currentStep]);

  return (
    <div ref={contentRef} tabIndex={-1} className="flex min-h-0 flex-1 flex-col outline-none" aria-live="polite">
      {/* Прогресс показывает плашка плана справа сверху; строка держит под неё место. */}
      <div className="mb-3 flex min-h-11 shrink-0 items-center gap-3 pr-[calc(min(300px,100vw-9rem)+1.5rem)]">
        <div className="flex min-w-0 flex-1 items-baseline gap-3">
          <p className="min-w-0 truncate text-xs font-bold uppercase tracking-wider text-primary">{phaseLabel}</p>
          {position && (
            <div className="hidden min-w-0 truncate text-sm font-semibold text-foreground md:block">
              {plainLessonText(position.episode.title)}
            </div>
          )}
        </div>
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.3 }}
          className="min-h-0 flex-1"
        >
          <FitToViewport resetKey={`${currentStep}-${retryKeys[currentStep] || 0}`}>
            <LessonStepCard
              activeBlocks={activeBlocks}
              activeOriginalIndices={activeOriginalIndices}
              answers={answers}
              attemptsByStep={attemptsByStep}
              currentStep={currentStep}
              maxOpenedStep={maxOpenedStep}
              retryKeys={retryKeys}
              onAnswer={onAnswer}
              onNavigate={onNavigate}
              onSaveIntermediate={onSaveIntermediate}
              onSetAnswers={onSetAnswers}
              onSetRetryKeys={onSetRetryKeys}
              lessonDocument={lessonDocument}
              activeBeatId={activeBeatId}
              onTeachingBeatChange={onTeachingBeatChange}
            />
          </FitToViewport>
        </motion.div>
      </AnimatePresence>
      <LessonContinueBar
        canContinue={!blockIsAssessment || answers[originalIndex] !== undefined}
        isLastStep={currentStep === activeBlocks.length - 1}
        isCompleted={isCompleted}
        isDiagnosticRoute={isDiagnosticRoute}
        onNext={onNext}
        onOpenSummary={onOpenSummary}
        leading={tutor || cue ? (
          // Один персонаж: рассказчик урока (аватар) и помощник-тьютор — в одной плашке.
          <TutorDock tutor={tutor} companion={{
            cue, previewImageUrl: lessonDocument?.avatar.preview_image_url, name: lessonDocument?.avatar.profile_name,
            lessonVersionId, avatarEnabled, audioEnabled, onAvatarEnabledChange, onAudioEnabledChange,
          }} />
        ) : null}
      />
    </div>
  );
}

function FitToViewport({ children, resetKey }: { children: ReactNode; resetKey: string }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const measuredContentRef = useRef<HTMLDivElement>(null);
  const scaleRef = useRef(1);
  const [scale, setScale] = useState(1);
  const [scaledHeight, setScaledHeight] = useState(0);

  const measure = useCallback(() => {
    const viewport = viewportRef.current;
    const measuredContent = measuredContentRef.current;
    if (!viewport || !measuredContent) return;

    const availableHeight = viewport.clientHeight;
    const requiredHeight = measuredContent.scrollHeight;
    const targetScale = availableHeight > 0 && requiredHeight > availableHeight
      ? Math.max(0.82, availableHeight / requiredHeight)
      : 1;
    // Expanding the content width to compensate for scaling can change text
    // wrapping by a few pixels. Never grow again during the same measurement
    // cycle, otherwise ResizeObserver can oscillate forever around that wrap.
    const nextScale = targetScale < scaleRef.current - 0.002 ? targetScale : scaleRef.current;
    scaleRef.current = nextScale;
    setScale(nextScale);
    setScaledHeight(Math.ceil(requiredHeight * nextScale));
  }, []);

  useLayoutEffect(() => {
    scaleRef.current = 1;
    setScale(1);
    setScaledHeight(0);
    const animationFrame = window.requestAnimationFrame(measure);
    let viewportFrame = 0;
    // Масштаб меняет вёрстку, поэтому меняем его в следующем кадре, а не в колбэке:
    // иначе ResizeObserver зацикливается и браузер сыплет ошибками.
    const viewportObserver = new ResizeObserver(() => {
      window.cancelAnimationFrame(viewportFrame);
      viewportFrame = window.requestAnimationFrame(() => {
        setScale(1);
        viewportFrame = window.requestAnimationFrame(measure);
      });
    });
    let contentFrame = 0;
    const contentObserver = new ResizeObserver(() => {
      window.cancelAnimationFrame(contentFrame);
      contentFrame = window.requestAnimationFrame(measure);
    });
    if (viewportRef.current) viewportObserver.observe(viewportRef.current);
    if (measuredContentRef.current) contentObserver.observe(measuredContentRef.current);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.cancelAnimationFrame(viewportFrame);
      window.cancelAnimationFrame(contentFrame);
      viewportObserver.disconnect();
      contentObserver.disconnect();
    };
  }, [measure, resetKey]);

  return (
    <div
      ref={viewportRef}
      className="relative h-full min-h-0 overflow-y-auto overflow-x-hidden outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      data-testid="lesson-step-viewport"
      aria-label="Материал текущего шага"
      tabIndex={0}
    >
      <div className="relative min-h-full" style={{ height: scaledHeight > 0 ? `${scaledHeight}px` : undefined }}>
        <div
          ref={measuredContentRef}
          className="absolute left-0 top-0"
          data-fit-scale={scale.toFixed(3)}
          style={{
            width: `${100 / scale}%`,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

type LessonStepCardProps = Omit<ActiveLessonContentProps,
  'contentRef' | 'prefersReducedMotion' | 'avatarEnabled' | 'audioEnabled' |
  'onAvatarEnabledChange' | 'onAudioEnabledChange' | 'isCompleted' | 'isDiagnosticRoute' | 'onNext' | 'onOpenSummary' | 'tutor'>;

function LessonStepCard({
  activeBlocks,
  activeOriginalIndices,
  answers,
  attemptsByStep,
  currentStep,
  retryKeys,
  onAnswer,
  onNavigate,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
  activeBeatId,
  onTeachingBeatChange,
}: LessonStepCardProps) {
  const tutorBridge = useTutorBridge();
  const block = activeBlocks[currentStep];
  const Component = componentMap[block.component];
  if (!Component) return <div className="text-destructive">Неизвестный блок</div>;

  const isAssessment = isAssessmentBlock(block);
  const originalIndex = activeOriginalIndices[currentStep] ?? currentStep;
  const isAnswered = answers[originalIndex] !== undefined;
  const isCorrect = answers[originalIndex] === true;

  const injectProps = isAssessment
    ? {
      onAnswer: (correct: boolean, detail?: { questionIndex: number; isFinished: boolean }) => {
        if (block.component === 'MasteryCheck' && detail) {
          if (!detail.isFinished) {
            const intermediateAnswers = { ...answers, [`${originalIndex}_q${detail.questionIndex}`]: correct };
            onSetAnswers(intermediateAnswers);
            onSaveIntermediate(intermediateAnswers, attemptsByStep);
            return;
          }

          onAnswer(currentStep, correct);
          return;
        }

        onAnswer(currentStep, correct);
      },
    }
    : {};
  const tutorProps = tutorAttemptProps(block.component, tutorBridge, originalIndex, currentStep);
  const synchronizationProps = block.component === 'Presentation'
    ? { activeBeatId, onTeachingBeatChange }
    : {};

  return (
    <div key={`block-${currentStep}-${retryKeys[currentStep] || 0}`} className="w-full min-w-0">
      <BlockMedia block={block} />
      <Suspense fallback={<LessonBlockFallback />}>
        <Component {...block.content} {...injectProps} {...tutorProps} {...synchronizationProps} />
      </Suspense>

      {isAssessment && isAnswered && !isCorrect && (
        <div className="mt-5 border-t border-border pt-4">
          <AssessmentRetryPanel
            answers={answers}
            attemptsByStep={attemptsByStep}
            currentStep={currentStep}
            originalIndex={originalIndex}
            onNavigate={onNavigate}
            onSaveIntermediate={onSaveIntermediate}
            onSetAnswers={onSetAnswers}
            onSetRetryKeys={onSetRetryKeys}
            theoryStep={findNearestExplanation(activeBlocks, currentStep)}
          />
        </div>
      )}
    </div>
  );
}

type LessonContinueBarProps = {
  canContinue: boolean;
  isLastStep: boolean;
  isCompleted: boolean;
  isDiagnosticRoute: boolean;
  onNext: () => void;
  onOpenSummary: () => void;
  /** Слева от кнопки (на телефоне — над ней): помощник урока. */
  leading?: ReactNode;
};

/** Кнопка «Продолжить» всегда в одном месте, под шагом, независимо от высоты контента. */
function LessonContinueBar({ canContinue, isLastStep, isCompleted, isDiagnosticRoute, onNext, onOpenSummary, leading }: LessonContinueBarProps) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border/60 pt-3 lg:gap-6">
      {leading && <div className="min-w-0 flex-1">{leading}</div>}
      <div className={`ml-auto flex justify-end ${leading ? '' : 'pr-20 sm:pr-0'}`}>
        <button
          type="button"
          disabled={!canContinue}
          title={canContinue ? undefined : 'Сначала ответьте на задание'}
          onClick={() => (isLastStep && isCompleted ? onOpenSummary() : onNext())}
          className={`flex items-center justify-center gap-2 py-3.5 ${leading
            // Рядом с помощником — в стилистике его плашки: тёмная «таблетка».
            ? 'h-12 rounded-[26px] border border-white/10 bg-neutral-900/95 px-5 text-white shadow-2xl hover:bg-neutral-800 sm:w-[240px] sm:px-8'
            : 'w-[240px] rounded-xl bg-primary px-8 text-primary-foreground shadow-sm hover:bg-primary/90'} font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-40`}
        >
          {isLastStep ? (isDiagnosticRoute ? 'Начать урок' : 'Завершить урок') : 'Продолжить'}
          <ChevronDown className="h-5 w-5 -rotate-90" />
        </button>
      </div>
    </div>
  );
}

type AssessmentRetryPanelProps = {
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  currentStep: number;
  originalIndex: number;
  theoryStep: number;
  onNavigate: (index: number) => void;
  onSaveIntermediate: (answers: LessonAnswers, attempts: AttemptsByStep) => void;
  onSetAnswers: (answers: LessonAnswers) => void;
  onSetRetryKeys: React.Dispatch<React.SetStateAction<Record<number, number>>>;
};

function AssessmentRetryPanel({
  answers,
  attemptsByStep,
  currentStep,
  originalIndex,
  theoryStep,
  onNavigate,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
}: AssessmentRetryPanelProps) {
  return (
    <div className="w-full p-4 rounded-xl bg-destructive/5 border border-destructive/20 mb-4 flex flex-col sm:flex-row gap-4 justify-between items-center">
      <div className="text-sm font-medium text-destructive">Материал требует повторения.</div>
      <div className="flex gap-3">
        <button
          onClick={() => onNavigate(theoryStep)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-background border border-border rounded-lg text-sm font-semibold shadow-sm hover:bg-muted transition-colors"
        >
          <BookMarked className="w-4 h-4" /> Повторить теорию
        </button>
        <button
          onClick={() => {
            const nextAnswers = Object.fromEntries(
              Object.entries(answers).filter(([key]) => (
                key !== String(originalIndex) && !key.startsWith(`${originalIndex}_q`)
              )),
            );
            onSetAnswers(nextAnswers);
            onSetRetryKeys((prev) => ({ ...prev, [currentStep]: (prev[currentStep] || 0) + 1 }));
            onSaveIntermediate(nextAnswers, attemptsByStep);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold shadow-sm hover:bg-primary/90 transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Попробовать снова
        </button>
      </div>
    </div>
  );
}

function LessonBlockFallback(): ReactNode {
  return (
    <div className="rounded-xl border border-border/60 bg-muted/20 p-6 text-sm font-medium text-muted-foreground">
      Загрузка блока...
    </div>
  );
}

function plainLessonText(value: string) {
  return narrationSpeechText(value) || value;
}

function findNearestExplanation(activeBlocks: Block[], currentIndex: number): number {
  for (let i = currentIndex - 1; i >= 0; i -= 1) {
    if (!isAssessmentBlock(activeBlocks[i])) {
      return i;
    }
  }
  return 0;
}
