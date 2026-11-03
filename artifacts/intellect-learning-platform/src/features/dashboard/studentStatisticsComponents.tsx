import { Activity, BookOpen, CheckCircle2, ChevronDown, Clock3, Target } from 'lucide-react';
import type { StudentReportLesson, StudentReportSubject, StudentReportSummary } from '@/lib/api/dashboard';
import { StudentLessonBreakdown } from './studentStatisticsBreakdown';
import { formatReportDate, formatReportDuration, formatReportScore, lessonNeedsPractice, lessonStateLabel } from './studentStatisticsModel';

export function StatisticsMetrics({ summary }: { summary: StudentReportSummary }) {
  const metrics = [
    { label: 'Пройдено уроков', value: summary.completed, Icon: CheckCircle2, color: 'text-emerald-600 bg-emerald-500/10' },
    { label: 'В процессе', value: summary.in_progress, Icon: Activity, color: 'text-blue-600 bg-blue-500/10' },
    { label: 'Средний результат', value: formatReportScore(summary.average_score), Icon: Target, color: 'text-primary bg-primary/10' },
    { label: 'Нужна практика', value: summary.needs_practice, Icon: BookOpen, color: 'text-amber-700 bg-amber-500/10' },
  ];
  return <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{metrics.map(({ label, value, Icon, color }) => <div key={label} className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5">
    <div className={`mb-3 grid h-9 w-9 place-items-center rounded-xl ${color}`}><Icon className="h-5 w-5" aria-hidden /></div>
    <dt className="text-xs font-semibold text-muted-foreground sm:text-sm">{label}</dt>
    <dd className="mt-1 break-words text-xl font-bold tracking-tight sm:text-2xl">{value}</dd>
  </div>)}</dl>;
}

export function SubjectStatisticsCard({ subject, selected, onSelect }: { subject: StudentReportSubject; selected: boolean; onSelect: () => void }) {
  const { summary } = subject;
  return <button type="button" onClick={onSelect} aria-pressed={selected} className={`min-h-11 min-w-0 rounded-2xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${selected ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-card hover:border-primary/40'}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0"><h3 className="break-words font-bold [overflow-wrap:anywhere]">{subject.name}</h3><p className="mt-0.5 text-xs text-muted-foreground">{subject.grade} класс</p></div>
      {selected && <CheckCircle2 className="h-5 w-5 shrink-0 text-primary" aria-hidden />}
    </div>
    <div className="mt-4 flex flex-wrap items-end justify-between gap-2 text-sm"><span><strong>{summary.completed_published}</strong><span className="text-muted-foreground"> / {summary.total_published} готовых уроков</span></span><span className="font-bold text-primary">{summary.total_published ? `${summary.progress_percent}%` : '—'}</span></div>
    <div role="progressbar" aria-label={`Прогресс: ${subject.name}, ${subject.grade} класс`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={summary.progress_percent} className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, Math.max(0, summary.progress_percent))}%` }} /></div>
    <div className="mt-3 flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs"><span className="text-muted-foreground">Средний: <strong className="text-foreground">{formatReportScore(summary.average_score)}</strong></span><span className={summary.needs_practice ? 'font-semibold text-amber-700 dark:text-amber-300' : 'text-muted-foreground'}>Нужна практика: {summary.needs_practice}</span></div>
  </button>;
}

export function StatisticsLessonCard({ lesson, studentId, open, onToggle }: { lesson: StudentReportLesson; studentId: number; open: boolean; onToggle: () => void }) {
  const result = lesson.last_completed ?? (lesson.status === 'completed' ? { score: lesson.score, completed_at: lesson.completed_at, elapsed_time_sec: lesson.elapsed_time_sec, mastery_status: lesson.mastery_status } : null);
  const mastery = result?.mastery_status ?? lesson.mastery_status;
  const masteryLabel = mastery === 'mastered' ? 'Цели освоены' : lessonNeedsPractice(lesson) ? 'Нужна практика' : 'Цели не проверены';
  return <li className={`min-w-0 overflow-hidden rounded-2xl border bg-card ${open ? 'border-primary/40' : 'border-border'}`}>
    <div className="min-w-0 p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0"><p className="mb-1 text-xs font-medium text-muted-foreground">{lesson.subject_name} · {lesson.subject_grade} класс{lesson.archived ? ' · Архив' : !lesson.published ? ' · Сейчас не опубликован' : ''}</p><h3 className="break-words font-bold leading-snug [overflow-wrap:anywhere]">{lesson.name}</h3></div>
        <span className={`w-fit shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${lesson.status === 'completed' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : lesson.status === 'in_progress' ? 'bg-blue-500/10 text-blue-700 dark:text-blue-300' : 'bg-muted text-muted-foreground'}`}>{lessonStateLabel(lesson)}</span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="font-bold">{result ? formatReportScore(result.score) : 'Нет завершённого результата'}</span>
        <span className={`rounded-md px-2 py-1 text-xs font-medium ${mastery === 'mastered' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : lessonNeedsPractice(lesson) ? 'bg-amber-500/10 text-amber-800 dark:text-amber-300' : 'bg-muted text-muted-foreground'}`}>{masteryLabel}</span>
        {result && <span className="text-xs text-muted-foreground">{formatReportDate(result.completed_at)}</span>}
        {lesson.has_progress && <span title="Сохранённое время прохождения" className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Clock3 className="h-3.5 w-3.5" aria-hidden /><span className="sr-only">Сохранённое время: </span>{formatReportDuration(result?.elapsed_time_sec ?? lesson.elapsed_time_sec)}</span>}
      </div>
      {lesson.retrying && <p className="mt-2 text-xs text-muted-foreground">Показан последний завершённый результат. Новое прохождение ещё идёт.</p>}
      {lesson.has_progress && <button type="button" aria-expanded={open} aria-controls={`lesson-report-${lesson.topic_id}`} onClick={onToggle} className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg px-1 text-sm font-bold text-primary hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />{open ? 'Свернуть разбор' : 'Разбор заданий'}</button>}
    </div>
    {open && <div id={`lesson-report-${lesson.topic_id}`}><StudentLessonBreakdown studentId={studentId} topicId={lesson.topic_id} /></div>}
  </li>;
}
