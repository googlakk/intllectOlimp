import { Link } from 'wouter';
import { ArrowLeft } from 'lucide-react';
import type React from 'react';
import type { Block, LearningObjective, ObjectiveMastery } from '@/lib/api/types';
import type { AttemptsByStep, LessonAnswers } from './studentProgress';
import { ActiveLessonContent } from './studentLessonContent';
import {
  EmptyLessonState,
  LessonCompletionSummary,
  LessonLoadingState,
  LessonStepper,
} from './studentLessonViews';

type StudentLessonPageViewProps = {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  assessmentBlocksCount: number;
  attemptsByStep: AttemptsByStep;
  contentRef: React.RefObject<HTMLDivElement | null>;
  currentStep: number;
  isCompleted: boolean;
  isEmpty: boolean;
  isLoading: boolean;
  learningObjective: string;
  maxOpenedStep: number;
  objectiveMastery: Record<string, ObjectiveMastery>;
  objectives: LearningObjective[];
  prefersReducedMotion: boolean | null;
  result: { score: number; level: string } | null;
  retryKeys: Record<number, number>;
  saveError: Error | null;
  subjectId: string | undefined;
  topicTitle: string;
  onAnswer: (blockIndex: number, isCorrect: boolean) => void;
  onNavigate: (index: number) => void;
  onNext: () => void;
  onOpenSummary: () => void;
  onReviewAnswers: () => void;
  onSaveIntermediate: (answers: LessonAnswers, attempts: AttemptsByStep) => void;
  onSetAnswers: (answers: LessonAnswers) => void;
  onSetRetryKeys: React.Dispatch<React.SetStateAction<Record<number, number>>>;
};

export function StudentLessonPageView({
  activeBlocks,
  activeOriginalIndices,
  answers,
  assessmentBlocksCount,
  attemptsByStep,
  contentRef,
  currentStep,
  isCompleted,
  isEmpty,
  isLoading,
  learningObjective,
  maxOpenedStep,
  objectiveMastery,
  objectives,
  prefersReducedMotion,
  result,
  retryKeys,
  saveError,
  subjectId,
  topicTitle,
  onAnswer,
  onNavigate,
  onNext,
  onOpenSummary,
  onReviewAnswers,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
}: StudentLessonPageViewProps) {
  const showSummary = isCompleted && result && currentStep === activeBlocks.length;

  return (
    <div className="max-w-5xl mx-auto pb-24">
      <Link href={`/learn/${subjectId}`} className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Назад к программе
      </Link>

      <div className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden min-h-[500px]">
        <div className="h-48 bg-gradient-to-br from-primary/10 via-primary/5 to-transparent relative p-8 flex flex-col justify-end border-b border-border/50">
          <div className="absolute top-6 right-6 px-4 py-1.5 bg-card/80 backdrop-blur-sm rounded-full shadow-sm text-sm font-bold text-primary flex items-center gap-2 border border-border/50">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></div>
            Изучение
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mt-4 mb-2 leading-tight">{topicTitle}</h1>
          {learningObjective && (
            <p className="text-sm md:text-base text-muted-foreground max-w-2xl line-clamp-2">
              Цель: {learningObjective}
            </p>
          )}
        </div>

        <div className="p-6 md:p-10">
          {saveError && (
            <div role="alert" className="mb-6 rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-sm font-medium text-destructive">
              Прогресс пока не сохранён: {saveError.message}
            </div>
          )}
          {isLoading ? (
            <LessonLoadingState />
          ) : isEmpty ? (
            <EmptyLessonState />
          ) : showSummary ? (
            <LessonCompletionSummary
              assessmentBlocksCount={assessmentBlocksCount}
              objectiveMastery={objectiveMastery}
              objectives={objectives}
              result={result}
              subjectId={subjectId}
              onReviewAnswers={onReviewAnswers}
            />
          ) : (
            <div className="flex flex-col lg:flex-row gap-8 relative">
              <LessonStepper
                activeBlocks={activeBlocks}
                answers={answers}
                currentStep={currentStep}
                isCompleted={isCompleted}
                maxOpenedStep={maxOpenedStep}
                onNavigate={onNavigate}
                onOpenSummary={onOpenSummary}
              />
              <ActiveLessonContent
                activeBlocks={activeBlocks}
                activeOriginalIndices={activeOriginalIndices}
                answers={answers}
                attemptsByStep={attemptsByStep}
                contentRef={contentRef}
                currentStep={currentStep}
                isCompleted={isCompleted}
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
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
