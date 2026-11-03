import { useState } from 'react';
import { AlertTriangle, MessageCircle } from 'lucide-react';
import { useStudentTutorDialogue, useStudentTutorSummary, type StudentTutorTurn } from '@/lib/api';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { parseMathText } from '@/components/blocks/ShortExplanation';

const OUTCOMES: Record<string, string> = { correct: 'верно', incorrect: 'неверно', wrong_unit: 'не та единица' };
const SOURCES: Record<string, string> = {
  template: 'готовая фраза', hint: 'подсказка урока', llm: 'ИИ', fallback: 'запасная фраза', guard: 'заменено защитой',
};
const FLAGS: Record<string, string> = {
  distress: 'тревожное сообщение', cheating_request: 'просил готовый ответ', pii: 'личные данные', abuse: 'грубость',
};

export function formatTutorTime(value: string | null): string {
  if (!value) return '';
  return new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

/** Служебные пометки, которые видит только учитель. */
export function teacherNotes(turn: StudentTutorTurn): string[] {
  return [
    turn.diagnosis ? `Диагноз: ${turn.diagnosis}` : '',
    turn.misconception_code ? `Затруднение: ${turn.misconception_code}` : '',
    turn.leak_blocked ? 'Ответ задачи скрыт защитой' : '',
    FLAGS[turn.safety_flag] ?? '',
    turn.off_topic ? 'не по теме' : '',
    turn.action === 'call_teacher' ? 'Отмечено: нужен учитель' : '',
  ].filter(Boolean);
}

function TutorDialogue({ studentId, topic, onClose }: { studentId: number; topic: { id: number; name: string }; onClose: () => void }) {
  const { data, isLoading, isError } = useStudentTutorDialogue(studentId, topic.id);
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto [overflow-wrap:anywhere]">
        <DialogTitle>Диалог с помощником: {topic.name}</DialogTitle>
        <DialogDescription>Реплики ученика и помощника по заданиям урока. Серым — пометки только для учителя.</DialogDescription>
        {isLoading && <p>Загружаем диалог…</p>}
        {(isError || data?.available === false) && <p role="alert">Не удалось загрузить диалог.</p>}
        {data?.available && data.turns.length === 0 && <p className="text-muted-foreground">В этой теме диалога нет.</p>}
        <ol className="space-y-3">
          {data?.turns.map((turn, index) => {
            // Задание — это версия урока, блок и вопрос: после переиздания номера блоков могут значить другое.
            const previous = data.turns[index - 1];
            const newTask = !previous || previous.lesson_version_id !== turn.lesson_version_id
              || previous.block_index !== turn.block_index || previous.question_index !== turn.question_index;
            const notes = teacherNotes(turn);
            return (
              <li key={turn.id} className="space-y-1.5">
                {newTask && (
                  <p className="pt-2 text-xs font-bold uppercase tracking-wide text-primary">
                    Блок урока №{turn.block_index + 1}{turn.question_index !== null ? `, вопрос ${turn.question_index + 1}` : ''}
                    {previous && previous.lesson_version_id !== turn.lesson_version_id ? ' (новая версия урока)' : ''}
                  </p>
                )}
                {(turn.student_text || turn.student_value) && (
                  <p className="ml-auto w-fit max-w-[85%] rounded-2xl bg-primary px-3 py-2 text-sm text-primary-foreground">
                    {turn.student_text ?? `Ответ: ${turn.student_value}${turn.check_outcome ? ` (${OUTCOMES[turn.check_outcome] ?? turn.check_outcome})` : ''}`}
                  </p>
                )}
                {turn.reply && (
                  <p className="w-fit max-w-[85%] rounded-2xl bg-muted px-3 py-2 text-sm">
                    {parseMathText(turn.reply)}
                    <span className="mt-1 block text-[11px] text-muted-foreground">
                      {SOURCES[turn.source] ?? turn.source} · {formatTutorTime(turn.created_at)}
                    </span>
                  </p>
                )}
                {notes.length > 0 && <p className="text-xs text-muted-foreground">{notes.join(' · ')}</p>}
              </li>
            );
          })}
        </ol>
      </DialogContent>
    </Dialog>
  );
}

/** Раздел «Помощник» в отчёте об ученике. */
export function StudentTutorReport({ studentId }: { studentId: number }) {
  const { data, isLoading, isError, refetch } = useStudentTutorSummary(studentId);
  const [openTopic, setOpenTopic] = useState<{ id: number; name: string } | null>(null);
  const topicName = (id: number) => data?.topics.find((topic) => topic.topic_id === id)?.name ?? `Тема ${id}`;

  return (
    <section className="min-w-0 space-y-3 [overflow-wrap:anywhere]" aria-label="Помощник">
      <h3 className="flex items-center gap-2 font-semibold"><MessageCircle className="h-4 w-4 text-primary" aria-hidden /> Помощник (ИИ-тьютор)</h3>
      {isLoading && <p>Загружаем диалоги…</p>}
      {isError && <p role="alert">Не удалось загрузить данные помощника. <button className="min-h-11 underline text-primary" onClick={() => refetch()}>Повторить</button></p>}
      {data && !data.available && <p className="text-muted-foreground">Журнал помощника пока недоступен.</p>}
      {data?.available && data.topics.length === 0 && <p className="text-muted-foreground">Ученик ещё не обращался к помощнику.</p>}

      {data?.available && data.alerts.length > 0 && (
        <div role="region" aria-label="Нужно внимание учителя" className="space-y-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3">
          <p className="flex items-center gap-2 text-sm font-bold text-destructive"><AlertTriangle className="h-4 w-4" aria-hidden /> Нужно внимание учителя</p>
          <ul className="space-y-1 text-sm">
            {data.alerts.map((alert) => (
              <li key={alert.turn_id}>
                <strong>{alert.kind === 'distress' ? 'Тревожное сообщение' : 'Нужна помощь учителя'}</strong>
                {' — '}{topicName(alert.topic_id)}, {formatTutorTime(alert.created_at)}
                {alert.student_text && <span className="text-muted-foreground">: «{alert.student_text}»</span>}
                {' '}<button className="min-h-11 underline text-primary" onClick={() => setOpenTopic({ id: alert.topic_id, name: topicName(alert.topic_id) })}>Открыть диалог</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data?.available && data.topics.length > 0 && (
        <ul className="grid min-w-0 gap-3 lg:grid-cols-2">
          {data.topics.map((topic) => (
            <li key={topic.topic_id} className="min-w-0 rounded-xl border border-border p-4">
              <p className="break-words text-sm font-semibold [overflow-wrap:anywhere]">{topic.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">{formatTutorTime(topic.last_at)}</p>
              <dl className="my-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs sm:grid-cols-4">
                <div><dt className="text-muted-foreground">Вопросы</dt><dd className="mt-1 font-bold">{topic.messages}</dd></div>
                <div><dt className="text-muted-foreground">Подсказки</dt><dd className="mt-1 font-bold">{topic.hints}</dd></div>
                <div><dt className="text-muted-foreground">Нужен учитель</dt><dd className="mt-1 font-bold">{topic.teacher_calls || '—'}</dd></div>
                <div><dt className="text-muted-foreground">Пометки</dt><dd className="mt-1 font-bold">{topic.safety_flags + topic.leaks_blocked || '—'}</dd></div>
              </dl>
              <button className="min-h-11 rounded-lg pr-3 text-sm font-semibold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => setOpenTopic({ id: topic.topic_id, name: topic.name })}>Показать диалог</button>
            </li>
          ))}
        </ul>
      )}

      {data?.available && data.misconceptions.length > 0 && (
        <p className="text-sm"><span className="font-semibold">Частые затруднения: </span>
          {data.misconceptions.map((item) => `${item.code} (${item.count})`).join(', ')}</p>
      )}

      {openTopic && <TutorDialogue studentId={studentId} topic={openTopic} onClose={() => setOpenTopic(null)} />}
    </section>
  );
}
