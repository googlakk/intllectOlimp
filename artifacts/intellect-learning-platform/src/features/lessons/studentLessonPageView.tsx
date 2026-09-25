import { Link } from 'wouter';
import { ArrowLeft, ListTree, X } from 'lucide-react';
import { useCallback, useEffect, useState, type ReactNode, type RefObject, type Dispatch, type SetStateAction } from 'react';
import type { Block, LearningObjective, LessonDocument, ObjectiveMastery, WarpGate } from '@/lib/api/types';
import type { AttemptsByStep, LessonAnswers } from './studentProgress';
import { ActiveLessonContent } from './studentLessonContent';
import { LessonTitlePage } from './LessonTitlePage';
import type { LessonIntro } from './lessonIntro';
import { AvatarCompanion } from './AvatarCompanion';
import { TutorCard, TutorMobileButton } from '@/features/tutor/TutorPanel';
import type { LessonTutor } from '@/features/tutor/useLessonTutor';
import { avatarCueForBeat, defaultBeatId, lessonPositionForBlock } from './lessonExperience';
import {
  EmptyLessonState,
  LessonCompletionSummary,
  LessonLoadingState,
  LessonStepper,
  LessonUnavailableState,
} from './studentLessonViews';

type StudentLessonPageViewProps = {
  learningContext?: ReactNode;
  /** Титульная страница: пока она есть, урок ещё не начат. */
  intro?: LessonIntro | null;
  onStartLesson?: () => void;
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  assessmentBlocksCount: number;
  attemptsByStep: AttemptsByStep;
  contentRef: RefObject<HTMLDivElement | null>;
  currentStep: number;
  isCompleted: boolean;
  isDiagnosticRoute: boolean;
  isEmpty: boolean;
  isLoading: boolean;
  loadError: Error | null;
  learningObjective: string;
  lessonDocument?: LessonDocument;
  lessonVersionId?: number | null;
  maxOpenedStep: number;
  objectiveMastery: Record<string, ObjectiveMastery>;
  objectives: LearningObjective[];
  prefersReducedMotion: boolean | null;
  result: { score: number; level: string } | null;
  retryKeys: Record<number, number>;
  saveError: Error | null;
  subjectId: string | undefined;
  topicTitle: string;
  warpGates?: WarpGate[];
  onAnswer: (blockIndex: number, isCorrect: boolean) => void;
  onNavigate: (index: number) => void;
  onNext: () => void;
  onOpenSummary: () => void;
  onReviewAnswers: () => void;
  onRestart: () => void;
  isRestarting: boolean;
  restartError: Error | null;
  onSaveIntermediate: (answers: LessonAnswers, attempts: AttemptsByStep) => void;
  onSetAnswers: (answers: LessonAnswers) => void;
  onSetRetryKeys: Dispatch<SetStateAction<Record<number, number>>>;
  avatarEnabled: boolean;
  audioEnabled: boolean;
  onAvatarEnabledChange: (enabled: boolean) => void;
  onAudioEnabledChange: (enabled: boolean) => void;
  /** Помощник урока — только когда он включён для ученика. */
  tutor?: LessonTutor;
};

export function StudentLessonPageView({
  intro,
  onStartLesson,
  learningContext,
  activeBlocks,
  activeOriginalIndices,
  answers,
  assessmentBlocksCount,
  attemptsByStep,
  contentRef,
  currentStep,
  isCompleted,
  isDiagnosticRoute,
  isEmpty,
  isLoading,
  loadError,
  learningObjective,
  lessonDocument,
  lessonVersionId,
  maxOpenedStep,
  objectiveMastery,
  objectives,
  prefersReducedMotion,
  result,
  retryKeys,
  saveError,
  subjectId,
  topicTitle,
  warpGates,
  onAnswer,
  onNavigate,
  onNext,
  onOpenSummary,
  onReviewAnswers,
  onRestart,
  isRestarting,
  restartError,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
  avatarEnabled,
  audioEnabled,
  onAvatarEnabledChange,
  onAudioEnabledChange,
  tutor,
}: StudentLessonPageViewProps) {
  const showSummary = isCompleted && result && currentStep === activeBlocks.length;
  const [isPlanOpen, setIsPlanOpen] = useState(false);
  const [activeBeatId, setActiveBeatId] = useState<string>();
  const activeOriginalIndex = activeOriginalIndices[currentStep] ?? currentStep;
  const lessonPosition = lessonPositionForBlock(lessonDocument, activeOriginalIndex);
  const sceneDefaultBeatId = defaultBeatId(lessonPosition?.scene);
  const effectiveBeatId = lessonPosition?.scene.teaching_beats?.some((beat) => beat.id === activeBeatId)
    ? activeBeatId
    : sceneDefaultBeatId;
  const avatarCue = avatarCueForBeat(lessonPosition?.scene, effectiveBeatId);
  const showIntro = Boolean(intro && onStartLesson && !isLoading && !loadError && !isEmpty && !showSummary);
  const showLessonRail = !isLoading && !isEmpty && !showSummary && !showIntro;
  const handleTeachingBeatChange = useCallback((beatId: string) => setActiveBeatId(beatId), []);

  useEffect(() => {
    setActiveBeatId(sceneDefaultBeatId);
  }, [currentStep, lessonPosition?.scene.id, sceneDefaultBeatId]);

  useEffect(() => {
    setIsPlanOpen(window.matchMedia('(min-width: 1024px)').matches);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  let content: ReactNode;
  if (isLoading) {
    content = <LessonLoadingState />;
  } else if (loadError) {
    content = <LessonUnavailableState message={loadError.message} />;
  } else if (isEmpty) {
    content = <EmptyLessonState />;
  } else if (showIntro && intro && onStartLesson) {
    content = <LessonTitlePage intro={intro} onStart={onStartLesson} />;
  } else if (showSummary) {
    content = (
      <LessonCompletionSummary
        assessmentBlocksCount={assessmentBlocksCount}
        objectiveMastery={objectiveMastery}
        objectives={objectives}
        result={result}
        subjectId={subjectId}
        warpGates={warpGates}
        onReviewAnswers={onReviewAnswers}
        onRestart={onRestart}
        isRestarting={isRestarting}
        restartError={restartError}
      />
    );
  } else {
    content = (
      <ActiveLessonContent
        activeBlocks={activeBlocks}
        activeOriginalIndices={activeOriginalIndices}
        answers={answers}
        attemptsByStep={attemptsByStep}
        contentRef={contentRef}
        currentStep={currentStep}
        isCompleted={isCompleted}
        isDiagnosticRoute={isDiagnosticRoute}
        lessonDocument={lessonDocument}
        lessonVersionId={lessonVersionId}
        activeBeatId={effectiveBeatId}
        onTeachingBeatChange={handleTeachingBeatChange}
        maxOpenedStep={maxOpenedStep}
        prefersReducedMotion={prefersReducedMotion}
        retryKeys={retryKeys}
        onAnswer={onAnswer}
        onNavigate={onNavigate}
        onNext={onNext}
        onOpenSummary={onOpenSummary}
        onSaveIntermediate={onSaveIntermediate}
        onSetAnswers={onSetAnswers}
        onSetRetryKeys={onSetRetryKeys}
        avatarEnabled={avatarEnabled}
        audioEnabled={audioEnabled}
        onAvatarEnabledChange={onAvatarEnabledChange}
        onAudioEnabledChange={onAudioEnabledChange}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-[60] flex min-h-0 flex-col bg-background">
      <header className="z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card/95 px-3 backdrop-blur md:px-6">
        <Link
          href={`/learn/${subjectId}`}
          title="Назад к программе"
          aria-label="Назад к программе"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-bold text-foreground md:text-lg">{topicTitle}</h1>
          {learningObjective && (
            <p className="hidden truncate text-xs text-muted-foreground sm:block">Цель: {learningObjective}</p>
          )}
        </div>
        <div className="hidden items-center gap-2 text-xs font-semibold text-muted-foreground md:flex">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Урок идёт
        </div>
        <button
          type="button"
          title={isPlanOpen ? 'Скрыть план урока' : 'Показать план урока'}
          aria-label={isPlanOpen ? 'Скрыть план урока' : 'Показать план урока'}
          aria-expanded={isPlanOpen}
          onClick={() => setIsPlanOpen((open) => !open)}
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-md border transition-colors ${
            isPlanOpen ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'
          }`}
        >
          <ListTree className="h-5 w-5" />
        </button>
      </header>

      <div className="lesson-board relative flex min-h-0 flex-1 overflow-hidden">
        <main className={`h-full min-w-0 flex-1 flex-col px-4 py-4 sm:px-6 md:px-8 lg:px-10 xl:px-12 2xl:px-16 ${isPlanOpen ? 'hidden lg:flex' : 'flex'} ${showSummary ? 'overflow-y-auto' : 'overflow-hidden'}`}>
          {saveError && (
            <div role="alert" className="mb-6 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm font-medium text-destructive">
              Прогресс пока не сохранён: {saveError.message}
            </div>
          )}
          {currentStep === 0 && !showIntro && learningContext && <div className="max-h-[40vh] shrink-0 overflow-y-auto">{learningContext}</div>}
          {content}
        </main>

        {showLessonRail && (
          <aside
            aria-label="Дополнительные инструменты урока"
            className={`${isPlanOpen ? 'flex' : 'hidden lg:flex'} h-full w-full shrink-0 flex-col gap-4 overflow-hidden p-3 lg:w-[340px] lg:py-4 lg:pr-4 xl:w-[360px]`}
          >
            {isPlanOpen && (
              <section className={`flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-md ${avatarCue || tutor ? 'lg:flex-none lg:basis-1/2' : ''}`} aria-label="План урока">
                <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
                  <div>
                    <p className="text-sm font-bold text-foreground">План урока</p>
                    <p className="text-xs text-muted-foreground">Шаг {Math.min(currentStep + 1, activeBlocks.length)} из {activeBlocks.length}</p>
                  </div>
                  <button
                    type="button"
                    title="Скрыть план урока"
                    aria-label="Скрыть план урока"
                    onClick={() => setIsPlanOpen(false)}
                    className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-3">
                  <LessonStepper
                    activeBlocks={activeBlocks}
                    activeOriginalIndices={activeOriginalIndices}
                    answers={answers}
                    currentStep={currentStep}
                    isCompleted={isCompleted}
                    maxOpenedStep={maxOpenedStep}
                    lessonDocument={lessonDocument}
                    onNavigate={(index) => {
                      onNavigate(index);
                      if (window.innerWidth < 1024) setIsPlanOpen(false);
                    }}
                    onOpenSummary={onOpenSummary}
                  />
                </div>
              </section>
            )}

            {avatarCue && (
              <div className={`hidden min-h-0 overflow-y-auto rounded-2xl border border-border bg-card p-3 shadow-md lg:flex lg:flex-col lg:justify-center ${tutor ? 'lg:shrink-0' : isPlanOpen ? 'flex-1' : 'h-full'}`}>
                <AvatarCompanion
                  cue={avatarCue}
                  previewImageUrl={lessonDocument?.avatar.preview_image_url}
                  companionName={lessonDocument?.avatar.profile_name}
                  lessonVersionId={lessonVersionId}
                  avatarEnabled={avatarEnabled}
                  audioEnabled={audioEnabled}
                  onAvatarEnabledChange={onAvatarEnabledChange}
                  onAudioEnabledChange={onAudioEnabledChange}
                />
              </div>
            )}

            {tutor && <TutorCard tutor={tutor} />}
          </aside>
        )}
        {showLessonRail && tutor && <TutorMobileButton tutor={tutor} />}
      </div>
    </div>
  );
}
