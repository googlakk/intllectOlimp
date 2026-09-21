import { BookMarked, ChevronDown, RefreshCw } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Suspense, type ReactNode } from 'react';
import type React from 'react';
import { componentMap } from '@/components/blocks/BlockRenderer';
import type { Block } from '@/lib/api/types';
import { isAssessmentBlock, type AttemptsByStep, type LessonAnswers } from './studentProgress';

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
};

type ActiveLessonContentProps = {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  contentRef: React.RefObject<HTMLDivElement | null>;
  currentStep: number;
  isCompleted: boolean;
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
};

export function ActiveLessonContent({
  activeBlocks,
  activeOriginalIndices,
  answers,
  attemptsByStep,
  contentRef,
  currentStep,
  isCompleted,
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
}: ActiveLessonContentProps) {
  const block = activeBlocks[currentStep];
  const phaseLabel = PHASE_LABELS[block?.component] || 'Учебный шаг';

  return (
    <div ref={contentRef} tabIndex={-1} className="flex-1 outline-none" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-primary">{phaseLabel}</p>
          <p className="text-sm text-muted-foreground mt-1">
            Шаг {currentStep + 1} из {activeBlocks.length}
          </p>
        </div>
        <div
          className="w-full sm:w-48 h-2 rounded-full bg-muted overflow-hidden"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={activeBlocks.length}
          aria-valuenow={currentStep + 1}
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${((currentStep + 1) / activeBlocks.length) * 100}%` }}
          />
        </div>
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.3 }}
          className="space-y-8"
        >
          <LessonStepCard
            activeBlocks={activeBlocks}
            activeOriginalIndices={activeOriginalIndices}
            answers={answers}
            attemptsByStep={attemptsByStep}
            currentStep={currentStep}
            isCompleted={isCompleted}
            maxOpenedStep={maxOpenedStep}
            retryKeys={retryKeys}
            onAnswer={onAnswer}
            onNavigate={onNavigate}
            onNext={onNext}
            onOpenSummary={onOpenSummary}
            onSaveIntermediate={onSaveIntermediate}
            onSetAnswers={onSetAnswers}
            onSetRetryKeys={onSetRetryKeys}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

type LessonStepCardProps = Omit<ActiveLessonContentProps, 'contentRef' | 'prefersReducedMotion'>;

function LessonStepCard({
  activeBlocks,
  activeOriginalIndices,
  answers,
  attemptsByStep,
  currentStep,
  isCompleted,
  maxOpenedStep,
  retryKeys,
  onAnswer,
  onNavigate,
  onNext,
  onOpenSummary,
  onSaveIntermediate,
  onSetAnswers,
  onSetRetryKeys,
}: LessonStepCardProps) {
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

  return (
    <div key={`block-${currentStep}-${retryKeys[currentStep] || 0}`} className="bg-card rounded-2xl border border-border/50 shadow-sm p-6 lg:p-8">
      <Suspense fallback={<LessonBlockFallback />}>
        <Component {...block.content} {...injectProps} />
      </Suspense>

      <div className="mt-8 pt-6 border-t border-border flex flex-wrap gap-4 items-center justify-between">
        {isAssessment && isAnswered && !isCorrect && (
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
        )}

        {(!isAssessment || isAnswered) && (
          <div className="w-full flex justify-end">
            <button
              onClick={() => {
                if (currentStep === activeBlocks.length - 1 && isCompleted) {
                  onOpenSummary();
                } else {
                  onNext();
                }
              }}
              className="px-8 py-3.5 bg-primary text-primary-foreground font-bold rounded-xl shadow-sm hover:bg-primary/90 hover:-translate-y-0.5 transition-all flex items-center gap-2"
            >
              {currentStep === activeBlocks.length - 1 ? 'Завершить урок' : 'Продолжить'}
              <ChevronDown className="w-5 h-5 -rotate-90" />
            </button>
          </div>
        )}
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

function findNearestExplanation(activeBlocks: Block[], currentIndex: number): number {
  for (let i = currentIndex - 1; i >= 0; i -= 1) {
    if (!isAssessmentBlock(activeBlocks[i])) {
      return i;
    }
  }
  return 0;
}
