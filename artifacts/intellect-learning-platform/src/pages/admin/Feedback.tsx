import { useState } from 'react';
import { MessageSquareText } from 'lucide-react';
import { useLessonFeedbackList } from '@/lib/api';
import { FeedbackCard, FeedbackSummary } from '@/features/feedback/FeedbackList';

export default function Feedback() {
  const [onlyErrors, setOnlyErrors] = useState(false);
  const { data, isLoading, isError, refetch } = useLessonFeedbackList(onlyErrors);
  const tab = (active: boolean) => `rounded-lg px-4 py-2 text-sm font-semibold ${active ? 'bg-primary text-primary-foreground' : 'border hover:bg-muted'}`;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-bold"><MessageSquareText className="h-6 w-6 text-primary" aria-hidden /> Отзывы об уроках</h1>
        <p className="text-muted-foreground">Ученики оценивают урок в конце и сообщают об ошибках. Ответ необязателен, поэтому отзыв есть не у каждого прохождения.</p>
      </header>
      {isLoading && <p>Загружаем отзывы…</p>}
      {isError && <p role="alert">Не удалось загрузить отзывы. <button className="underline text-primary" onClick={() => refetch()}>Повторить</button></p>}
      {data && !data.available && (
        <p role="alert" className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
          Таблица отзывов ещё не создана: примените миграцию <code>20260927100000_lesson_feedback.sql</code>.
        </p>
      )}
      {data?.available && <>
        <FeedbackSummary summary={data.summary} />
        <div className="flex gap-2" role="tablist" aria-label="Фильтр отзывов">
          <button type="button" role="tab" aria-selected={!onlyErrors} onClick={() => setOnlyErrors(false)} className={tab(!onlyErrors)}>Все</button>
          <button type="button" role="tab" aria-selected={onlyErrors} onClick={() => setOnlyErrors(true)} className={tab(onlyErrors)}>С ошибками</button>
        </div>
        {data.items.length === 0
          ? <p className="text-muted-foreground">{onlyErrors ? 'Об ошибках пока не сообщали.' : 'Отзывов пока нет.'}</p>
          : <ul className="space-y-3">{data.items.map((item) => <FeedbackCard key={item.id} item={item} />)}</ul>}
      </>}
    </div>
  );
}
