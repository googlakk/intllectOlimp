import type { Topic } from '@/lib/api';
import { BatchGenerationDialog } from './BatchGenerationDialog';
import { GenerationBatchList } from './GenerationBatchList';
import { generationBlockReason, hasDraftMaterials } from './batchGenerationModel';
import type { useBatchGeneration } from './useBatchGeneration';

export function BatchGenerationControls({ subjectId, topics, workflow }: {
  subjectId: number; topics: Topic[]; workflow: ReturnType<typeof useBatchGeneration>;
}) {
  const candidates = topics.filter(topic => !hasDraftMaterials(topic) && !generationBlockReason(topic, workflow.active.get(topic.id)));
  return <div className="space-y-5">
    <div className="space-y-3 rounded-xl border bg-card p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold">Создать несколько уроков</h3><p className="text-sm text-muted-foreground">Отметьте темы в программе — до 30 за один запуск.</p></div><div className="flex flex-wrap gap-2"><button disabled={!candidates.length || workflow.start.isPending} onClick={() => workflow.select(candidates.map(topic => topic.id))} className="rounded-lg border px-3 py-2 text-sm">Выбрать темы без материалов</button><button disabled={!workflow.selectedTopics.length || workflow.start.isPending} onClick={workflow.openDialog} className="rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground disabled:opacity-50">Создать выбранные ({workflow.selectedTopics.length})</button>{workflow.selectedIds.length > 0 && <button disabled={workflow.start.isPending} onClick={() => workflow.select([])} className="rounded-lg border px-3 py-2 text-sm">Снять выбор</button>}</div></div>{workflow.message && <p role="status" className="text-sm">{workflow.message}</p>}{workflow.batches.isError && <p role="alert" className="text-sm text-destructive">Не удалось проверить очередь. <button onClick={() => void workflow.batches.refetch()} className="underline">Обновить</button></p>}</div>
    <GenerationBatchList subjectId={subjectId} batches={workflow.batches.data || []} topics={topics} onRetry={workflow.select} />
    {workflow.dialogOpen && <BatchGenerationDialog topics={workflow.selectedTopics} onClose={() => workflow.setDialogOpen(false)} onSubmit={workflow.submit} pending={workflow.start.isPending} error={workflow.start.error?.message} />}
  </div>;
}
