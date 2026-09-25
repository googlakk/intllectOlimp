import { useStudentLearningReport } from '@/lib/api';
import { StudentTutorReport } from './StudentTutorReport';

export function StudentLearningReport({ studentId, onClose }: { studentId: number; onClose: () => void }) {
  const { data, isLoading, isError, refetch } = useStudentLearningReport(studentId);
  return <section className="rounded-2xl border border-primary/30 bg-card p-6 space-y-4" aria-label="Отчёт по ученику">
    <div className="flex justify-between gap-4"><h2 className="text-xl font-bold">{data?.name || 'Результаты ученика'}</h2><button onClick={onClose} className="text-primary font-semibold">Закрыть</button></div>
    {isLoading && <p>Загружаем результаты…</p>}
    {isError && <p role="alert">Не удалось загрузить отчёт. <button className="underline text-primary" onClick={() => refetch()}>Повторить</button></p>}
    {data && <><h3 className="font-semibold">Проверенные навыки</h3>{data.skills.length === 0 && <p className="text-muted-foreground">Пока нет подтверждённых измерений навыков.</p>}
      <ul className="space-y-2">{data.skills.map(skill => <li key={skill.id}>{skill.name} — <strong>{skill.status === 'mastered' ? 'Освоен' : 'Нужна практика'}</strong> <span className="text-muted-foreground">({skill.evidence_count} проверок)</span></li>)}</ul>
      <h3 className="font-semibold">Занятия и темы, которым нужна помощь</h3>
      <ul className="space-y-2">{data.lessons.map(lesson => <li key={lesson.topic_id}>{lesson.name}{lesson.archived ? ' (архив)' : ''} — {lesson.status === 'completed' ? 'Пройдено' : 'В процессе'}; {lesson.mastery_status === 'needs_practice' ? 'Нужна помощь' : lesson.mastery_status === 'mastered' ? 'Цели освоены' : 'Цели ещё не проверены'}</li>)}</ul>
      <StudentTutorReport studentId={studentId} />
    </>}
  </section>;
}
