import { Link } from 'wouter';
import { Loader2 } from 'lucide-react';
import { useCancelLessonGenerationBatch, type LessonGenerationBatch, type Topic } from '@/lib/api';
import { activeGenerationItems, batchFinishedCount, generationStatusLabels, retryableBatchTopics } from './batchGenerationModel';

export function GenerationBatchList({ subjectId, batches, topics, onRetry }: {
  subjectId: number; batches: LessonGenerationBatch[]; topics: Topic[]; onRetry: (ids: number[]) => void;
}) {
  const cancel = useCancelLessonGenerationBatch(subjectId);
  if (!batches.length) return null;
  const active = activeGenerationItems(batches);
  const visible = [...batches.filter(batch => batch.counts.running + batch.counts.queued > 0),
    ...batches.filter(batch => batch.counts.running + batch.counts.queued === 0).slice(0, 3)];
  return <section aria-label="Фоновая подготовка уроков" className="space-y-3">
    <h3 className="text-lg font-bold">Фоновая подготовка</h3>
    <p className="text-sm text-muted-foreground">Очередь работает на сервере. Обновление страницы сохраняет результаты; ошибки не запускают повторную генерацию.</p>
    {cancel.error && <p role="alert" className="text-sm text-destructive">{cancel.error.message}</p>}
    {visible.map(batch => {
      const finished = batchFinishedCount(batch);
      const busy = batch.counts.queued + batch.counts.running > 0;
      const retries = retryableBatchTopics(batch, topics, active);
      return <details key={batch.batch_id} open={busy || undefined} className="rounded-xl border bg-card p-4">
        <summary className="cursor-pointer font-semibold">{busy ? 'Готовим уроки' : batch.counts.failed ? 'Подготовка завершена с ошибками' : batch.counts.cancelled ? 'Очередь остановлена' : 'Уроки готовы'} · {finished} из {batch.total} завершено</summary>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm"><span>Готово: {batch.counts.succeeded}</span><span>В очереди: {batch.counts.queued}</span><span>Создаётся: {batch.counts.running}</span>{batch.counts.failed > 0 && <span className="text-destructive">Ошибок: {batch.counts.failed}</span>}</div>
        <progress aria-label="Обработано уроков" max={batch.total || 1} value={finished} className="mt-3 h-2 w-full accent-primary" />
        <ul className="mt-3 divide-y">{batch.items.map(item => <li key={item.topic_id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><div className="min-w-0"><p className="font-semibold">{item.topic_name}</p>{item.error && <p className="mt-1 text-destructive">{item.error}</p>}</div><div className="flex items-center gap-2"><span role="status" className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1">{item.status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}{generationStatusLabels[item.status]}</span>{item.status === 'succeeded' && <Link href={`/dashboard/lessons/${item.topic_id}`} className="font-semibold text-primary underline">Открыть черновик</Link>}</div></li>)}</ul>
        <div className="mt-3 flex flex-wrap gap-2">{batch.counts.queued > 0 && <button disabled={cancel.isPending} onClick={() => cancel.mutate(batch.batch_id)} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{cancel.isPending && cancel.variables === batch.batch_id ? 'Останавливаем…' : 'Остановить очередь'}</button>}{retries.length > 0 && <button onClick={() => onRetry(retries)} className="rounded-lg border px-3 py-2 text-sm">Выбрать уроки с ошибками ({retries.length})</button>}</div>
        {batch.counts.queued > 0 && <p className="mt-2 text-xs text-muted-foreground">При остановке отменяются только уроки в очереди. Уже начатые завершатся.</p>}
      </details>;
    })}
  </section>;
}
