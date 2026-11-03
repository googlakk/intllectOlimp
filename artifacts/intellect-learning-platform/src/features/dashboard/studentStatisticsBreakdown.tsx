import { CheckCircle2, CircleHelp, Loader2 } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { useStudentLessonReport, type StudentAttemptDetail, type StudentReportQuestion } from '@/lib/api/dashboard';
import { ApiError } from '@/lib/api/client';
import { formatReportDate, formatReportDuration, formatReportScore } from './studentStatisticsModel';

const STAGES: Record<string, string> = { diagnostic: 'Диагностика', practice: 'Тренировка', assessment: 'Итоговая проверка' };
const OUTCOMES: Record<string, { label: string; color: string }> = {
  correct: { label: 'Верно', color: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' },
  incorrect: { label: 'Неверно', color: 'bg-red-500/10 text-red-700 dark:text-red-300' },
  wrong_unit: { label: 'Ошибка в единицах', color: 'bg-amber-500/10 text-amber-800 dark:text-amber-300' },
  assisted: { label: 'С помощью образца', color: 'bg-violet-500/10 text-violet-700 dark:text-violet-300' },
  skipped: { label: 'Пропущено', color: 'bg-muted text-muted-foreground' },
};

function ReportQuestion({ question, index }: { question: StudentReportQuestion; index: number }) {
  const outcome = OUTCOMES[question.outcome ?? ''];
  return (
    <li className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h5 className="text-sm font-bold">Задание {index + 1} <span className="font-medium text-muted-foreground">· {STAGES[question.stage] ?? 'Задание'}</span></h5>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${outcome?.color ?? 'bg-muted text-muted-foreground'}`}>{outcome?.label ?? 'Не проверено'}</span>
      </div>
      {['support', 'challenge'].includes(question.variant ?? '') && <p className="mb-2 text-xs font-medium text-muted-foreground">{question.variant === 'support' ? 'Вариант с поддержкой' : 'Вариант повышенной сложности'}</p>}
      <RichText text={question.prompt || 'Условие задания недоступно'} className="max-w-full overflow-x-auto break-words text-sm leading-relaxed [overflow-wrap:anywhere]" />
      <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-2">
        <div className="min-w-0 rounded-xl bg-muted/40 p-3">
          <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-foreground">Ответ ученика</p>
          {question.response !== null
            ? <div className="max-w-full overflow-x-auto whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">{parseMathText(question.response || 'Пустой ответ')}</div>
            : <p className="text-sm text-muted-foreground">{question.outcome ? 'Ответ не сохранялся' : 'Ответ пока не отправлен'}</p>}
        </div>
        {question.expected && <div className="min-w-0 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
          <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-foreground">Правильный ответ / критерий</p>
          <RichText text={question.expected} className="max-w-full overflow-x-auto whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]" />
        </div>}
      </div>
      {question.explanation && <details className="mt-3 text-sm">
        <summary className="inline-flex min-h-11 cursor-pointer items-center gap-2 font-semibold text-primary"><CircleHelp className="h-4 w-4" aria-hidden />Объяснение решения</summary>
        <RichText text={question.explanation} className="mt-2 max-w-full overflow-x-auto break-words leading-relaxed [overflow-wrap:anywhere]" />
      </details>}
      {question.attempts != null && <p className="mt-3 text-xs text-muted-foreground">Сохранённых попыток проверки: {question.attempts}</p>}
    </li>
  );
}

function AttemptDetail({ attempt, title }: { attempt: StudentAttemptDetail; title: string }) {
  return (
    <section className="min-w-0 space-y-4" aria-label={title}>
      <div>
        <h4 className="font-bold">{title}</h4>
        <p className="mt-1 text-sm text-muted-foreground">
          {attempt.status === 'completed' ? `Результат: ${formatReportScore(attempt.score)} · ${formatReportDate(attempt.completed_at)}` : 'Ответы текущего прохождения'}
          {' · '}Сохранённое время: {formatReportDuration(attempt.elapsed_time_sec)}
        </p>
      </div>
      {!attempt.version_available && <p role="status" className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-sm">Версия задания недоступна. Показаны только сохранённые ответы и результаты проверки.</p>}
      {attempt.objectives.length > 0 && <div className="rounded-xl border border-border bg-card p-4">
        <h5 className="mb-3 text-sm font-bold">Учебные цели</h5>
        <ul className="space-y-3">{attempt.objectives.map(objective => <li key={objective.id} className="flex items-start gap-2 text-sm">
          <CheckCircle2 className={`mt-0.5 h-4 w-4 shrink-0 ${objective.status === 'mastered' ? 'text-emerald-600' : 'text-muted-foreground'}`} aria-hidden />
          <div className="min-w-0"><RichText text={objective.text} className="break-words [overflow-wrap:anywhere]" /><p className="mt-1 text-xs font-medium text-muted-foreground">{objective.status === 'mastered' ? 'Освоена' : objective.status === 'needs_practice' ? 'Нужна практика' : objective.status === 'in_progress' ? 'В процессе' : 'Не проверена'}{objective.score !== null && ['mastered', 'needs_practice', 'in_progress'].includes(objective.status) ? ` · ${formatReportScore(objective.score)}` : ''}</p></div>
        </li>)}</ul>
      </div>}
      {attempt.questions.length > 0
        ? <ol className="space-y-3">{attempt.questions.map((question, index) => <ReportQuestion key={question.key} question={question} index={index} />)}</ol>
        : <p className="text-sm text-muted-foreground">Нет сохранённых оценочных заданий для разбора.</p>}
    </section>
  );
}

export function StudentLessonBreakdown({ studentId, topicId }: { studentId: number; topicId: number }) {
  const { data, isLoading, error, refetch } = useStudentLessonReport(studentId, topicId);
  if (isLoading) return <p role="status" className="flex items-center gap-2 p-4 text-sm"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />Загружаем разбор заданий…</p>;
  if (error) return <div role="alert" className="p-4 text-sm">
    <p>{error instanceof ApiError && [403, 404].includes(error.status) ? 'Результаты этого урока недоступны.' : 'Не удалось загрузить разбор заданий.'}</p>
    <button className="min-h-11 font-semibold text-primary" onClick={() => refetch()}>Повторить загрузку</button>
  </div>;
  if (!data) return null;
  return <div className="min-w-0 space-y-5 border-t border-border bg-muted/20 p-4 sm:p-5">
    {data.current ? <AttemptDetail attempt={data.current} title={data.current.status === 'completed' ? 'Завершённое прохождение' : 'Текущее прохождение'} /> : <p className="text-sm text-muted-foreground">Ученик пока не начал этот урок.</p>}
    {data.last_completed && data.current?.status !== 'completed' && <details className="min-w-0 rounded-xl border border-border p-4" open>
      <summary className="min-h-11 cursor-pointer font-bold">Последний завершённый результат</summary>
      <div className="mt-3"><AttemptDetail attempt={data.last_completed} title="Последнее завершённое прохождение" /></div>
    </details>}
  </div>;
}
