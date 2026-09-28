import { useEffect } from 'react';
import { Link } from 'wouter';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { useGetLesson, useTopic } from '@/lib/api';

export default function PresenterView({ topicId }: { topicId: number }) {
  const topicQuery = useTopic(topicId);
  const lessonQuery = useGetLesson(topicId, 'teacher');
  const topic = topicQuery.data;
  const lesson = lessonQuery.data;
  const blocks = lesson?.blocks ?? [];
  const title = topic?.name || lesson?.lesson_document?.title || 'Урок';
  const backHref = `/dashboard/lessons/${topicId}`;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return (
    <div className="fixed inset-0 z-[60] flex min-h-0 flex-col overflow-y-auto bg-background">
      <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card/95 px-4 backdrop-blur md:px-8">
        <Link
          href={backHref}
          title="Назад к редактированию"
          aria-label="Назад к редактированию"
          className="rounded-md px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          ← Назад
        </Link>
        <h1 className="truncate text-lg font-bold">{title}</h1>
      </header>
      <main className="flex-1 px-4 py-8 md:px-8">
        {lessonQuery.isLoading || topicQuery.isLoading ? (
          <p role="status" className="text-center text-sm font-semibold text-muted-foreground">
            Загрузка урока…
          </p>
        ) : lessonQuery.error || topicQuery.error ? (
          <div role="alert" className="mx-auto max-w-lg rounded-lg border p-6 text-center">
            <p className="mb-3">Не удалось загрузить урок.</p>
            <button
              type="button"
              onClick={() => {
                void lessonQuery.refetch();
                void topicQuery.refetch();
              }}
              className="rounded-lg border px-4 py-2 font-semibold underline"
            >
              Повторить
            </button>
          </div>
        ) : topic?.archived_at ? (
          <p className="text-center">Этот урок в архиве. Восстановите тему в программе, чтобы показать урок.</p>
        ) : blocks.length === 0 ? (
          <div className="mx-auto max-w-lg text-center">
            <p className="mb-3">В этом уроке пока нет материалов.</p>
            <Link href={backHref} className="font-semibold underline">
              Перейти к редактированию
            </Link>
          </div>
        ) : (
          <BlockRenderer blocks={blocks} />
        )}
      </main>
    </div>
  );
}
