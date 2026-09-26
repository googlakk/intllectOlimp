import { CheckCircle2, CircleDashed, X } from 'lucide-react';
import { useStudentLearningReport } from '@/lib/api';
import type { StudentLearningReport as StudentLearningReportData } from '@/lib/api/dashboard';
import { StudentTutorReport } from './StudentTutorReport';

type Skill = StudentLearningReportData['skills'][number];
type Lesson = StudentLearningReportData['lessons'][number];

/** Навык — плитка с полосой освоения, а не строка текста: видно сразу, без чтения статуса словами. */
function SkillTile({ skill }: { skill: Skill }) {
  const mastered = skill.status === 'mastered';
  const percent = Math.round(Math.max(0, Math.min(1, skill.mastery_score ?? (mastered ? 1 : 0))) * 100);
  return (
    <li className="rounded-lg border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium leading-snug">{skill.name}</p>
        <span
          className={`shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${
            mastered ? 'bg-green-500/10 text-green-700 dark:text-green-400' : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
          }`}
        >
          {mastered ? 'Освоен' : 'Нужна практика'}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${mastered ? 'bg-green-500' : 'bg-amber-500'}`}
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {skill.evidence_count} {skill.evidence_count === 1 ? 'проверка' : 'проверок'}
        </span>
      </div>
    </li>
  );
}

const LESSON_MASTERY_LABEL: Record<string, { text: string; className: string }> = {
  mastered: { text: 'Цели освоены', className: 'bg-green-500/10 text-green-700 dark:text-green-400' },
  needs_practice: { text: 'Нужна помощь', className: 'bg-red-500/10 text-red-700 dark:text-red-400' },
};
const DEFAULT_LESSON_MASTERY = { text: 'Цели ещё не проверены', className: 'bg-muted text-muted-foreground' };

/** Занятие — строка со значком хода урока и отдельной плашкой освоения: это разные вопросы. */
function LessonRow({ lesson }: { lesson: Lesson }) {
  const mastery = LESSON_MASTERY_LABEL[lesson.mastery_status] ?? DEFAULT_LESSON_MASTERY;
  return (
    <li className="flex items-center gap-3 rounded-lg border bg-background p-3">
      {lesson.status === 'completed'
        ? <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" aria-label="пройдено" />
        : <CircleDashed className="h-5 w-5 shrink-0 text-muted-foreground" aria-label="в процессе" />}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{lesson.name}{lesson.archived ? ' (архив)' : ''}</p>
        <p className="text-xs text-muted-foreground">{lesson.status === 'completed' ? 'Пройдено' : 'В процессе'}</p>
      </div>
      <span className={`shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${mastery.className}`}>
        {mastery.text}
      </span>
    </li>
  );
}

export function StudentLearningReport({ studentId, onClose }: { studentId: number; onClose: () => void }) {
  const { data, isLoading, isError, refetch } = useStudentLearningReport(studentId);
  const skillsNeedingPractice = data?.skills.filter((skill) => skill.status !== 'mastered') ?? [];
  const skillsMastered = data?.skills.filter((skill) => skill.status === 'mastered') ?? [];

  return (
    <section className="rounded-2xl border border-primary/30 bg-card p-6 space-y-5" aria-label="Отчёт по ученику">
      <div className="flex justify-between gap-4">
        <h2 className="text-xl font-bold">{data?.name || 'Результаты ученика'}</h2>
        <button onClick={onClose} className="flex items-center gap-1 text-primary font-semibold">
          <X className="h-4 w-4" /> Закрыть
        </button>
      </div>
      {isLoading && <p>Загружаем результаты…</p>}
      {isError && <p role="alert">Не удалось загрузить отчёт. <button className="underline text-primary" onClick={() => refetch()}>Повторить</button></p>}
      {data && <>
        <div>
          <h3 className="mb-2 font-semibold">Проверенные навыки</h3>
          {data.skills.length === 0
            ? <p className="text-muted-foreground">Пока нет подтверждённых измерений навыков.</p>
            : <>
              {skillsNeedingPractice.length > 0 && (
                <ul className="space-y-2">{skillsNeedingPractice.map((skill) => <SkillTile key={skill.id} skill={skill} />)}</ul>
              )}
              {skillsMastered.length > 0 && (
                <details className="mt-2" open={skillsNeedingPractice.length === 0}>
                  <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
                    Освоено ({skillsMastered.length})
                  </summary>
                  <ul className="mt-2 space-y-2">{skillsMastered.map((skill) => <SkillTile key={skill.id} skill={skill} />)}</ul>
                </details>
              )}
            </>}
        </div>
        <div>
          <h3 className="mb-2 font-semibold">Занятия и темы, которым нужна помощь</h3>
          {data.lessons.length === 0
            ? <p className="text-muted-foreground">Ученик пока не начал ни одной темы.</p>
            : <ul className="space-y-2">{data.lessons.map((lesson) => <LessonRow key={lesson.topic_id} lesson={lesson} />)}</ul>}
        </div>
        <StudentTutorReport studentId={studentId} />
      </>}
    </section>
  );
}
