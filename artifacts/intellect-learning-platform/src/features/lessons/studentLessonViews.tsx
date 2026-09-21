import { Link } from 'wouter';
import { BookOpen, CheckCircle, Loader2, Trophy } from 'lucide-react';
import type { Block, LearningObjective, ObjectiveMastery } from '@/lib/api/types';
import { isAssessmentBlock, type LessonAnswers } from './studentProgress';

export function LessonLoadingState() {
  return (
    <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
      <Loader2 className="w-16 h-16 text-primary animate-spin mx-auto mb-6" />
      <h3 className="text-2xl font-bold text-foreground mb-3">Загрузка урока</h3>
    </div>
  );
}

export function EmptyLessonState() {
  return (
    <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
      <BookOpen className="w-16 h-16 text-muted-foreground/30 mx-auto mb-6" />
      <h3 className="text-2xl font-bold text-foreground mb-3">Урок готовится</h3>
      <p className="text-muted-foreground max-w-md mx-auto font-medium">
        Преподаватель еще не опубликовал этот урок. Возвращайтесь позже!
      </p>
    </div>
  );
}

type LessonCompletionSummaryProps = {
  result: { score: number; level: string };
  assessmentBlocksCount: number;
  objectives: LearningObjective[];
  objectiveMastery: Record<string, ObjectiveMastery>;
  subjectId: string | undefined;
  onReviewAnswers: () => void;
};

export function LessonCompletionSummary({
  result,
  assessmentBlocksCount,
  objectives,
  objectiveMastery,
  subjectId,
  onReviewAnswers,
}: LessonCompletionSummaryProps) {
  return (
    <div className="text-center py-20 border-2 border-dashed border-primary/30 rounded-3xl bg-primary/5 px-4 animate-in fade-in zoom-in duration-500">
      <CheckCircle className="w-20 h-20 text-primary mx-auto mb-6" />
      <h3 className="text-3xl font-extrabold text-foreground mb-4">Урок завершён!</h3>
      {assessmentBlocksCount > 0 && (
        <div className="flex flex-col items-center justify-center gap-4 mb-8">
          <div className="text-5xl font-black text-primary">{result.score}%</div>
          <div className="px-6 py-2 bg-card border border-border rounded-full text-lg font-bold text-foreground shadow-sm">
            Уровень: <span className="text-primary">{result.level}</span>
          </div>
        </div>
      )}
      {!assessmentBlocksCount && (
        <p className="text-muted-foreground font-medium mb-8">
          Урок завершён, но в нём нет оцениваемых заданий. Освоение целей не подтверждено.
        </p>
      )}
      {objectives.length > 0 && (
        <div data-testid="objective-results" className="mx-auto mb-8 max-w-2xl text-left">
          <h4 className="mb-3 text-sm font-bold uppercase tracking-wider text-muted-foreground">Результаты по целям</h4>
          <div className="space-y-2">
            {objectives.map((objective) => {
              const objectiveResult = objectiveMastery[objective.id];
              const mastered = objectiveResult?.status === 'mastered';
              return (
                <div data-testid={`objective-result-${objective.id}`} key={objective.id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3">
                  <span className="text-sm font-semibold text-foreground">{objective.text}</span>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${mastered ? 'bg-green-500/10 text-green-700 dark:text-green-400' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'}`}>
                    {mastered ? 'Освоено' : objectiveResult?.status === 'in_progress' ? 'В процессе' : objectiveResult?.status === 'not_assessed' ? 'Не оценено' : 'Нужна практика'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div className="flex gap-4 justify-center">
        <button
          onClick={onReviewAnswers}
          className="px-6 py-3 border border-border bg-card text-foreground font-bold rounded-xl shadow-sm hover:bg-muted transition-all"
        >
          Просмотреть ответы
        </button>
        <Link href={`/learn/${subjectId}`}>
          <button className="px-8 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all">
            Вернуться к курсу
          </button>
        </Link>
      </div>
    </div>
  );
}

type LessonStepperProps = {
  activeBlocks: Block[];
  answers: LessonAnswers;
  currentStep: number;
  isCompleted: boolean;
  maxOpenedStep: number;
  onNavigate: (index: number) => void;
  onOpenSummary: () => void;
};

export function LessonStepper({
  activeBlocks,
  answers,
  currentStep,
  isCompleted,
  maxOpenedStep,
  onNavigate,
  onOpenSummary,
}: LessonStepperProps) {
  return (
    <div className="w-full lg:w-64 shrink-0" aria-label="Прогресс урока">
      <div className="sticky top-8 flex flex-col gap-3">
        <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">Шаги урока</h3>
        {activeBlocks.slice(0, maxOpenedStep + 1).map((block, index) => {
          const isActive = index === currentStep;
          const isCompletedBlock = index < maxOpenedStep || answers[index] !== undefined;
          const isAssessment = isAssessmentBlock(block);

          return (
            <button
              key={index}
              onClick={() => onNavigate(index)}
              className={`text-left p-3 rounded-xl border transition-all duration-300 flex items-start gap-3 ${
                isActive
                  ? 'bg-primary/5 border-primary shadow-sm ring-1 ring-primary/20'
                  : 'bg-card border-border hover:border-primary/50'
              }`}
            >
              <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                isCompletedBlock ? 'bg-primary text-primary-foreground' : (isActive ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground')
              }`}>
                {isCompletedBlock ? <CheckCircle className="w-3.5 h-3.5" /> : index + 1}
              </div>
              <div className="flex-1 overflow-hidden">
                <div className={`text-sm font-semibold truncate ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {isAssessment ? 'Практика' : 'Теория'}
                </div>
              </div>
            </button>
          );
        })}
        {isCompleted && (
          <button
            onClick={onOpenSummary}
            className={`text-left p-3 rounded-xl border transition-all duration-300 flex items-start gap-3 mt-4 ${
              currentStep === activeBlocks.length
                ? 'bg-primary/5 border-primary shadow-sm ring-1 ring-primary/20'
                : 'bg-card border-border hover:border-primary/50'
            }`}
          >
            <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
              currentStep === activeBlocks.length ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
            }`}>
              <Trophy className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 overflow-hidden">
              <div className={`text-sm font-semibold truncate ${currentStep === activeBlocks.length ? 'text-foreground' : 'text-muted-foreground'}`}>
                Итоги
              </div>
            </div>
          </button>
        )}
      </div>
    </div>
  );
}
