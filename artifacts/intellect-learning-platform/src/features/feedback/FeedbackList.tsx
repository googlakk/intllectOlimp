import { AlertTriangle, Star } from 'lucide-react';
import { Link } from 'wouter';
import type { LessonFeedbackItem, LessonFeedbackList } from '@/lib/api';

function Stars({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted-foreground">без оценки</span>;
  return (
    <span className="flex items-center gap-0.5" aria-label={`Оценка ${value} из 5`}>
      {[1, 2, 3, 4, 5].map((index) => (
        <Star key={index} className={`h-4 w-4 ${index <= value ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/30'}`} />
      ))}
    </span>
  );
}

function formatDate(value: string | null): string {
  if (!value) return '';
  return new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function FeedbackSummary({ summary }: { summary: LessonFeedbackList['summary'] }) {
  const cards = [
    { label: 'Отзывов', value: String(summary.total) },
    { label: 'Средняя оценка', value: summary.average_rating !== null ? `${String(summary.average_rating).replace('.', ',')} из 5` : '—' },
    { label: 'Сообщили об ошибках', value: String(summary.with_errors) },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {cards.map((card) => (
        <div key={card.label} className="rounded-2xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">{card.label}</p>
          <p className="mt-1 text-2xl font-bold">{card.value}</p>
        </div>
      ))}
    </div>
  );
}

export function FeedbackCard({ item }: { item: LessonFeedbackItem }) {
  return (
    <li className="rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={`/dashboard/lessons/${item.topic_id}`} className="font-semibold hover:text-primary">{item.topic_name}</Link>
          <p className="text-sm text-muted-foreground">{item.subject_name} · {item.grade} класс · {item.student_name}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Stars value={item.rating} />
          <span className="text-xs text-muted-foreground">{formatDate(item.created_at)}</span>
        </div>
      </div>
      {item.had_errors !== null && (
        <p className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
          item.had_errors ? 'bg-red-500/10 text-red-700 dark:text-red-400' : 'bg-green-500/10 text-green-700 dark:text-green-400'
        }`}>
          {item.had_errors && <AlertTriangle className="h-3.5 w-3.5" />}
          {item.had_errors ? 'Были ошибки' : 'Ошибок не было'}
        </p>
      )}
      {item.comment && <p className="mt-3 whitespace-pre-wrap text-sm">{item.comment}</p>}
    </li>
  );
}
