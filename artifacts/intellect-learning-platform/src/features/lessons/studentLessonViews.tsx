import { Link } from 'wouter';
import { BookOpen, CheckCircle, Loader2, LockKeyhole, RotateCcw, Sparkles } from 'lucide-react';
import type { LearningObjective, ObjectiveMastery, WarpGate } from '@/lib/api/types';

export function LessonLoadingState() {
  return (
    <div
      data-testid="lesson-step-viewport"
      aria-label="Материал текущего шага загружается"
      className="flex h-full min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border/50 bg-card p-4 shadow-sm sm:p-5 lg:p-6"
      tabIndex={0}
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="h-3 w-32 rounded-full bg-primary/20" />
        <div className="h-2 w-28 rounded-full bg-muted" />
      </div>
      <div className="flex min-h-0 flex-1 flex-col justify-center gap-5 rounded-lg bg-muted/10 p-6">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <div className="space-y-3">
          <div className="h-8 w-2/3 max-w-xl rounded-md bg-muted" />
          <div className="h-4 w-full max-w-3xl rounded bg-muted/80" />
          <div className="h-4 w-5/6 max-w-2xl rounded bg-muted/70" />
        </div>
      </div>
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

export function LessonUnavailableState({ message }: { message: string }) {
  return (
    <div role="alert" className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
      <LockKeyhole className="w-16 h-16 text-muted-foreground/40 mx-auto mb-6" />
      <h3 className="text-2xl font-bold text-foreground mb-3">Тема пока закрыта</h3>
      <p className="text-muted-foreground max-w-md mx-auto font-medium">{message}</p>
    </div>
  );
}

type LessonCompletionSummaryProps = {
  result: { score: number; level: string };
  assessmentBlocksCount: number;
  objectives: LearningObjective[];
  objectiveMastery: Record<string, ObjectiveMastery>;
  subjectId: string | undefined;
  warpGates?: WarpGate[];
  onReviewAnswers: () => void;
  onRestart: () => void;
  isRestarting: boolean;
  restartError: Error | null;
};

export function LessonCompletionSummary({
  result,
  assessmentBlocksCount,
  objectives,
  objectiveMastery,
  subjectId,
  warpGates = [],
  onReviewAnswers,
  onRestart,
  isRestarting,
  restartError,
}: LessonCompletionSummaryProps) {
  const allObjectivesMastered = objectives.length > 0
    && objectives.every((objective) => objectiveMastery[objective.id]?.status === 'mastered');
  const masteredObjectivesCount = objectives.filter(
    (objective) => objectiveMastery[objective.id]?.status === 'mastered',
  ).length;
  const needsPractice = assessmentBlocksCount > 0 && !allObjectivesMastered;
  const title = allObjectivesMastered
    ? 'Тема освоена!'
    : assessmentBlocksCount > 0
      ? 'Попытка завершена'
      : 'Материал просмотрен';

  return (
    <div className="text-center py-20 border-2 border-dashed border-primary/30 rounded-3xl bg-primary/5 px-4 animate-in fade-in zoom-in duration-500">
      <CheckCircle className="w-20 h-20 text-primary mx-auto mb-6" />
      <h3 className="text-3xl font-extrabold text-foreground mb-4">{title}</h3>
      {assessmentBlocksCount > 0 && (
        <div className="flex flex-col items-center justify-center gap-4 mb-8">
          {objectives.length > 0 && !allObjectivesMastered ? (
            <>
              <div className="text-5xl font-black text-primary">{masteredObjectivesCount} / {objectives.length}</div>
              <div className="text-sm font-bold uppercase text-muted-foreground">освоено целей</div>
              <div className="rounded-full border border-border bg-card px-5 py-2 text-sm font-semibold text-foreground shadow-sm">
                Точность выполненных заданий: {result.score}%
              </div>
            </>
          ) : (
            <>
              <div className="text-5xl font-black text-primary">{result.score}%</div>
              <div className="px-6 py-2 bg-card border border-border rounded-full text-lg font-bold text-foreground shadow-sm">
                Уровень: <span className="text-primary">{result.level}</span>
              </div>
            </>
          )}
        </div>
      )}
      {!assessmentBlocksCount && (
        <p className="text-muted-foreground font-medium mb-8">
          Урок завершён, но в нём нет оцениваемых заданий. Освоение целей не подтверждено.
        </p>
      )}
      {needsPractice && (
        <p className="mx-auto mb-8 max-w-xl font-medium text-amber-800 dark:text-amber-300">
          Можно продолжить курс, но лучше разобрать ответы и закрыть неосвоенные цели новой попыткой.
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
      {warpGates.length > 0 && (
        <div className="mx-auto mb-8 max-w-2xl rounded-lg border border-primary/25 bg-card p-5 text-left shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-primary">
            <Sparkles className="h-5 w-5" />
            <h4 className="font-extrabold">Открылись новые возможности</h4>
          </div>
          <div className="space-y-3">
            {warpGates.map((gate) => (
              <div key={`${gate.from_topic_id}-${gate.to_topic_id}`} className="rounded-md border border-border bg-muted/20 p-4">
                <div className="font-bold text-foreground">{gate.topic_name}</div>
                <div className="mt-0.5 text-xs font-semibold uppercase text-primary">{gate.subject_name}</div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{gate.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {restartError && (
        <p role="alert" className="mx-auto mb-4 max-w-xl text-sm font-semibold text-destructive">
          Не удалось начать новую попытку: {restartError.message}
        </p>
      )}
      <div className="flex flex-wrap gap-4 justify-center">
        <button
          onClick={onReviewAnswers}
          className="px-6 py-3 border border-border bg-card text-foreground font-bold rounded-xl shadow-sm hover:bg-muted transition-all"
        >
          Просмотреть ответы
        </button>
        {needsPractice && (
          <button
            type="button"
            onClick={onRestart}
            disabled={isRestarting}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-6 py-3 font-bold text-white shadow-sm transition-colors hover:bg-amber-700 disabled:cursor-wait disabled:opacity-60"
          >
            {isRestarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            Пройти ещё раз
          </button>
        )}
        <Link href={`/learn/${subjectId}`}>
          <button className="px-8 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all">
            Вернуться к курсу
          </button>
        </Link>
      </div>
    </div>
  );
}

