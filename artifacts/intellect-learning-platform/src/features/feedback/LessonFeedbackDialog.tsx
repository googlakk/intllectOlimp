import { useEffect, useState } from 'react';
import { CheckCircle2, Star } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { useSubmitLessonFeedback } from '@/lib/api';
import { hasFeedback } from './feedbackPrompt';

const RATING_LABELS = ['', 'Плохо', 'Так себе', 'Нормально', 'Хорошо', 'Отлично'];

/** Отзыв в конце урока: всё необязательно, «Пропустить» закрывает окно без отправки. */
export function LessonFeedbackDialog({ open, onClose, topicId }: { open: boolean; onClose: () => void; topicId: number }) {
  const submit = useSubmitLessonFeedback();
  const [rating, setRating] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [hadErrors, setHadErrors] = useState<boolean | null>(null);
  const [comment, setComment] = useState('');
  const [thanked, setThanked] = useState(false);

  // После «Спасибо» окно закрывается само.
  useEffect(() => {
    if (!thanked) return;
    const timer = window.setTimeout(onClose, 1600);
    return () => window.clearTimeout(timer);
  }, [thanked, onClose]);

  const send = () => {
    submit.mutate(
      { topic_id: topicId, rating, had_errors: hadErrors, comment: comment.trim() || null },
      { onSuccess: () => setThanked(true) },
    );
  };

  const shown = hover ?? rating ?? 0;
  const choiceClass = (active: boolean) => `rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
    active ? 'border-primary bg-primary text-primary-foreground' : 'hover:border-primary/50 hover:bg-primary/5'
  }`;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent className="max-w-md">
        {thanked ? (
          <div className="flex flex-col items-center gap-3 py-6 text-center" role="status">
            <CheckCircle2 className="h-10 w-10 text-green-600" />
            <DialogTitle>Спасибо за отзыв!</DialogTitle>
            <DialogDescription>Он поможет сделать уроки лучше.</DialogDescription>
          </div>
        ) : (
          <>
            <DialogTitle>Как вам урок?</DialogTitle>
            <DialogDescription>Ответ необязателен — можно пропустить.</DialogDescription>

            <div className="space-y-5 pt-2">
              <div>
                <div className="flex items-center gap-1" role="radiogroup" aria-label="Оценка урока" onMouseLeave={() => setHover(null)}>
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={rating === value}
                      aria-label={`${value} из 5 — ${RATING_LABELS[value]}`}
                      onMouseEnter={() => setHover(value)}
                      onClick={() => setRating(rating === value ? null : value)}
                      className="rounded-md p-1 transition-transform hover:scale-110"
                    >
                      <Star className={`h-8 w-8 ${value <= shown ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/40'}`} />
                    </button>
                  ))}
                  <span className="ml-2 text-sm text-muted-foreground">{RATING_LABELS[shown]}</span>
                </div>
              </div>

              <div>
                <p className="mb-2 text-sm font-semibold">Были ли в уроке ошибки?</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setHadErrors(hadErrors === false ? null : false)} className={choiceClass(hadErrors === false)}>Нет</button>
                  <button type="button" onClick={() => setHadErrors(hadErrors === true ? null : true)} className={choiceClass(hadErrors === true)}>Да, были</button>
                </div>
              </div>

              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold">
                  {hadErrors ? 'Что было не так?' : 'Что понравилось или что улучшить?'}
                  <span className="font-normal text-muted-foreground"> — необязательно</span>
                </span>
                <textarea
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder={hadErrors ? 'Например: неверный ответ в задаче 3, опечатка, не сработала кнопка…' : 'Пара слов об уроке'}
                  className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </label>

              {submit.isError && <p role="alert" className="text-sm text-destructive">Не удалось отправить отзыв. Попробуйте ещё раз или пропустите.</p>}

              <div className="flex justify-end gap-2">
                <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground">
                  Пропустить
                </button>
                <button
                  type="button"
                  onClick={send}
                  disabled={!hasFeedback(rating, hadErrors, comment) || submit.isPending}
                  className="rounded-lg bg-primary px-5 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
                >
                  {submit.isPending ? 'Отправляем…' : 'Отправить'}
                </button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
