import { useEffect, useRef } from 'react';
import { Link, useParams, useSearchParams } from 'wouter';
import { ArrowLeft, Archive, BookOpen, Loader2, Search, ShieldAlert } from 'lucide-react';
import { useStudentLearningReport } from '@/lib/api/dashboard';
import { ApiError } from '@/lib/api/client';
import { StudentTutorReport } from './StudentTutorReport';
import { StatisticsLessonCard, StatisticsMetrics, SubjectStatisticsCard } from './studentStatisticsComponents';
import { filterReportLessons, LESSON_FILTERS, positiveId, readStatisticsFilters } from './studentStatisticsModel';

export function StudentStatisticsView() {
  const { studentId: rawId } = useParams();
  const studentId = positiveId(rawId);
  const { data, isLoading, error, refetch } = useStudentLearningReport(studentId);
  const [params, setParams] = useSearchParams();
  const rawFilters = readStatisticsFilters(params);
  const selectedSubject = data?.subjects.find(subject => subject.id === rawFilters.subjectId);
  const filters = { ...rawFilters, subjectId: selectedSubject?.id ?? null };
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
    headingRef.current?.focus({ preventScroll: true });
  }, [studentId]);

  const updateFilter = (key: string, value: string | null) => {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== 'topic') next.delete('topic');
      return next;
    }, { replace: true });
  };
  const lessons = filterReportLessons(data?.lessons ?? [], filters);
  const historicalLessons = filterReportLessons(data?.lessons ?? [], filters, true);
  const historicalOpen = historicalLessons.some(lesson => lesson.topic_id === filters.topicId);
  const summary = selectedSubject?.summary ?? data?.summary;
  const denied = error instanceof ApiError && [403, 404].includes(error.status);

  return <div className="mx-auto min-w-0 max-w-6xl space-y-6 pb-8 sm:space-y-8">
    <header className="min-w-0">
      <Link href="/dashboard" className="mb-3 inline-flex min-h-11 items-center gap-2 rounded-lg pr-3 text-sm font-semibold text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><ArrowLeft className="h-4 w-4" aria-hidden />Назад к списку</Link>
      <p className="mb-1 text-xs font-bold uppercase tracking-wider text-primary">Статистика ученика</p>
      <h1 ref={headingRef} tabIndex={-1} className="break-words text-2xl font-bold tracking-tight outline-none sm:text-3xl [overflow-wrap:anywhere]">{data?.name ?? 'Результаты ученика'}</h1>
      {data && <p className="mt-2 text-sm text-muted-foreground">{data.grade} класс · текущие результаты по доступным вам предметам</p>}
    </header>

    {isLoading && <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" aria-hidden />Загружаем статистику…</div>}
    {(!studentId || error) && <div role="alert" className="rounded-2xl border border-border bg-card p-6">
      <ShieldAlert className="mb-3 h-6 w-6 text-muted-foreground" aria-hidden />
      <h2 className="font-bold">{!studentId || denied ? 'Ученик недоступен' : 'Не удалось загрузить статистику'}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{!studentId || denied ? 'Проверьте ссылку. Просматривать можно только учеников и предметы, к которым у вас есть доступ.' : 'Попробуйте загрузить данные ещё раз.'}</p>
      {studentId && !denied && <button type="button" onClick={() => refetch()} className="mt-3 min-h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground">Повторить загрузку</button>}
    </div>}

    {data && !error && <>
      {summary && <section aria-label={selectedSubject ? `Сводка: ${selectedSubject.name}` : 'Общая сводка'} className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-bold">{selectedSubject ? `${selectedSubject.name} · ${selectedSubject.grade} класс` : 'Общая сводка'}</h2><span className="text-xs text-muted-foreground">По последним завершённым результатам</span></div>
        <StatisticsMetrics summary={summary} />
        <p className="text-xs leading-relaxed text-muted-foreground">Средний результат учитывает только оценённые завершённые уроки. Прохождение урока и освоение его целей показаны отдельно.</p>
      </section>}

      <section aria-labelledby="student-subjects-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="student-subjects-heading" className="text-xl font-bold">Предметы</h2><button type="button" aria-pressed={filters.subjectId === null} onClick={() => updateFilter('subject', null)} className={`min-h-11 rounded-xl border px-4 text-sm font-semibold ${filters.subjectId === null ? 'border-primary bg-primary/5 text-primary' : 'border-border bg-card text-muted-foreground'}`}>Все предметы</button></div>
        {data.subjects.length ? <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.subjects.map(subject => <SubjectStatisticsCard key={subject.id} subject={subject} selected={subject.id === filters.subjectId} onSelect={() => updateFilter('subject', String(subject.id))} />)}</div>
          : <div className="rounded-2xl border border-dashed border-border p-6 text-sm text-muted-foreground">Для текущего класса пока нет доступных программ.</div>}
      </section>

      <section aria-labelledby="student-lessons-heading" className="space-y-4">
        <div><h2 id="student-lessons-heading" className="text-xl font-bold">Уроки и результаты</h2><p className="mt-1 text-sm text-muted-foreground">{selectedSubject ? `${selectedSubject.name} · ${selectedSubject.grade} класс` : 'По всем предметам текущего класса'}</p></div>
        <label className="relative block"><span className="sr-only">Поиск урока</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden /><input type="search" value={filters.search} onChange={event => updateFilter('q', event.target.value || null)} placeholder="Найти урок по названию" className="min-h-11 w-full rounded-xl border border-border bg-card pl-10 pr-3 text-base outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" /></label>
        <div className="flex flex-wrap gap-2" aria-label="Фильтр результатов">{LESSON_FILTERS.map(filter => <button key={filter.value} type="button" aria-pressed={filters.status === filter.value} onClick={() => updateFilter('status', filter.value === 'all' ? null : filter.value)} className={`min-h-11 rounded-xl border px-3 text-sm font-semibold ${filters.status === filter.value ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground hover:text-foreground'}`}>{filter.label}</button>)}</div>
        {lessons.length ? <ul className="min-w-0 space-y-3">{lessons.map(lesson => <StatisticsLessonCard key={lesson.topic_id} lesson={lesson} studentId={studentId!} open={lesson.topic_id === filters.topicId} onToggle={() => updateFilter('topic', lesson.topic_id === filters.topicId ? null : String(lesson.topic_id))} />)}</ul>
          : <div className="rounded-2xl border border-dashed border-border p-6 text-center"><BookOpen className="mx-auto mb-3 h-7 w-7 text-muted-foreground" aria-hidden /><p className="font-semibold">{filters.search || filters.status !== 'all' ? 'Уроки по выбранным условиям не найдены' : 'Готовых уроков пока нет'}</p><p className="mt-2 text-sm text-muted-foreground">{filters.search || filters.status !== 'all' ? 'Измените поиск или фильтр.' : 'Результаты появятся, когда ученик начнёт опубликованные уроки.'}</p></div>}
      </section>

      {historicalLessons.length > 0 && <details className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5" open={historicalOpen || undefined}>
        <summary className="min-h-11 cursor-pointer font-bold"><span className="inline-flex items-center gap-2"><Archive className="h-4 w-4 text-muted-foreground" aria-hidden />Архив и другие программы ({historicalLessons.length})</span></summary>
        <p className="mb-4 mt-2 text-sm text-muted-foreground">Эти результаты сохранены, но не входят в текущую сводку и прогресс программы.</p>
        <ul className="space-y-3">{historicalLessons.map(lesson => <StatisticsLessonCard key={lesson.topic_id} lesson={lesson} studentId={studentId!} open={lesson.topic_id === filters.topicId} onToggle={() => updateFilter('topic', lesson.topic_id === filters.topicId ? null : String(lesson.topic_id))} />)}</ul>
      </details>}

      {data.skills.length > 0 && <details className="rounded-2xl border border-border bg-card p-4 sm:p-5">
        <summary className="min-h-11 cursor-pointer font-bold">Последние измерения навыков ({data.skills.length})</summary>
        <p className="mb-4 mt-2 text-sm text-muted-foreground">Навыки могут проверяться в разных предметах. Это отдельные измерения, а не предметные оценки.</p>
        <ul className="grid gap-3 sm:grid-cols-2">{data.skills.map(skill => {
          const percent = Math.round(Math.min(1, Math.max(0, skill.mastery_score)) * 100);
          return <li key={skill.id} className="min-w-0 rounded-xl border border-border p-3"><p className="break-words text-sm font-semibold">{skill.name}</p><p className="mt-1 text-xs text-muted-foreground">{skill.status === 'mastered' ? 'Освоен' : skill.status === 'developing' ? 'Развивается' : 'Нужна практика'} · проверок: {skill.evidence_count}</p><div className="mt-3 flex items-center gap-2"><div role="progressbar" aria-label={`Освоение навыка: ${skill.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} /></div><span className="text-xs font-medium text-muted-foreground">{percent}%</span></div></li>;
        })}</ul>
      </details>}

      <div className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5"><StudentTutorReport studentId={studentId!} /><p className="mt-4 text-xs text-muted-foreground">Журнал показывает доступные сохранённые обращения по всем вашим предметам; показатели могут охватывать только последние записи.</p></div>
    </>}
  </div>;
}
