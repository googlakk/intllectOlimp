import { useState } from 'react';
import { useLessonAttempts, type ProgressRecord } from '@/lib/api';

function TopicHistory({ item, studentId }: { item: ProgressRecord; studentId: number }) {
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError, refetch } = useLessonAttempts(studentId, item.topic_id, open);
  return <article className="border-b border-border py-4 last:border-0">
    <h3 className="font-semibold">{item.topic_name || 'Учебная тема'} {item.archived_at && <span className="text-sm text-muted-foreground">(в архиве)</span>}</h3>
    <p className="text-sm text-muted-foreground">{item.status === 'completed' ? 'Урок пройден' : 'Урок начат'} · {item.mastery_status === 'mastered' ? 'Проверенные цели освоены' : item.mastery_status === 'needs_practice' ? 'Нужна практика' : 'Освоение пока не подтверждено'}</p>
    <button className="mt-2 text-sm font-semibold text-primary" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Скрыть попытки' : 'История попыток'}</button>
    {open && <div className="mt-3 space-y-2 text-sm">
      {isLoading && <p>Загружаем попытки…</p>}
      {isError && <p role="alert">Не удалось загрузить историю. <button onClick={() => refetch()} className="text-primary underline">Повторить</button></p>}
      {data?.length === 0 && <p className="text-muted-foreground">Для прежних результатов подробная история не сохранялась. Новые завершённые попытки появятся здесь.</p>}
      {data?.map(attempt => <p key={attempt.id}>Попытка {attempt.attempt_number} · {new Date(attempt.completed_at).toLocaleDateString('ru-RU')} · {attempt.snapshot.score === null ? 'Без оценки' : `${attempt.snapshot.score}%`} · {attempt.snapshot.mastery_status === 'mastered' ? 'Цели освоены' : attempt.snapshot.mastery_status === 'needs_practice' ? 'Есть цели для повторения' : 'Освоение не подтверждено'}</p>)}
    </div>}
  </article>;
}

export function LearningHistory({ progress, studentId }: { progress: ProgressRecord[]; studentId: number }) {
  return <section className="rounded-2xl border border-border bg-card p-6"><h2 className="text-xl font-bold">Уроки и история результатов</h2><p className="mt-2 text-sm text-muted-foreground">Прохождение урока и освоение его целей учитываются отдельно. Результаты архивных занятий сохраняются.</p>{progress.map(item => <TopicHistory key={item.topic_id} item={item} studentId={studentId} />)}</section>;
}
