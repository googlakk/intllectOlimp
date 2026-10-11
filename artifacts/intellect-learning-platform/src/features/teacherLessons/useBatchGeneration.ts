import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { useLessonGenerationBatches, useStartLessonGenerationBatch, type Topic } from '@/lib/api';
import { activeGenerationItems, batchRequestFingerprint, selectGenerationTopics, MAX_BATCH_TOPICS } from './batchGenerationModel';
import type { BatchOptions } from './BatchGenerationDialog';

export function useBatchGeneration(subjectId: number, topics: Topic[]) {
  const { user } = useAuth();
  const client = useQueryClient();
  const batches = useLessonGenerationBatches(subjectId);
  const start = useStartLessonGenerationBatch(subjectId);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [message, setMessage] = useState('');
  const requestRef = useRef<{ fingerprint: string; id: string } | null>(null);
  const previousCompleted = useRef('');
  const active = useMemo(() => activeGenerationItems(batches.data || []), [batches.data]);
  const eligibleIds = selectGenerationTopics(selectedIds, topics, active).ids;
  const selectedTopics = topics.filter(topic => eligibleIds.includes(topic.id));
  useEffect(() => {
    // The response can be lost after server acceptance. A status read settles that ambiguity.
    if (!requestRef.current || start.isPending || !batches.data?.some(batch => batch.batch_id === requestRef.current?.id)) return;
    requestRef.current = null;
    setDialogOpen(false);
    setSelectedIds([]);
    setMessage('Уроки добавлены в очередь. Можно закрыть страницу.');
  }, [batches.data, start.isPending]);
  useEffect(() => {
    setSelectedIds(previous => {
      const next = selectGenerationTopics(previous, topics, active).ids;
      return next.length === previous.length && next.every((id, index) => id === previous[index]) ? previous : next;
    });
  }, [topics, active]);
  const completed = (batches.data || []).flatMap(batch => batch.items.filter(item => item.status === 'succeeded')
    .map(item => `${batch.batch_id}:${item.topic_id}:${item.job_id}`)).sort().join(',');
  useEffect(() => {
    if (completed === previousCompleted.current) return;
    previousCompleted.current = completed;
    void client.invalidateQueries({ queryKey: ['subject-outline', subjectId] });
    void client.invalidateQueries({ queryKey: ['lesson'] });
    void client.invalidateQueries({ queryKey: ['dashboard'] });
  }, [client, completed, subjectId]);
  const select = (ids: number[]) => {
    const eligible = selectGenerationTopics(ids, topics, active);
    if (eligible.limited) setMessage(`За один запуск можно выбрать до ${MAX_BATCH_TOPICS} уроков. Остальные можно добавить следующей группой.`);
    else setMessage('');
    setSelectedIds(eligible.ids);
  };
  const toggle = (topicId: number, checked: boolean) => select(checked ? [...selectedIds, topicId] : selectedIds.filter(id => id !== topicId));
  const submit = (options: BatchOptions) => {
    if (!user || !selectedTopics.length) return;
    const body = {
      subject_id: subjectId, topic_ids: selectedTopics.map(topic => topic.id), teacher_id: user.id,
      model: options.model, content_language: options.contentLanguage, replace_existing_drafts: options.replaceDrafts,
    };
    const fingerprint = batchRequestFingerprint(body);
    if (requestRef.current?.fingerprint !== fingerprint) requestRef.current = { fingerprint, id: crypto.randomUUID() };
    start.mutate({ ...body, request_id: requestRef.current!.id }, { onSuccess: () => {
      setDialogOpen(false); setSelectedIds([]); setMessage('Уроки добавлены в очередь. Можно закрыть страницу.'); requestRef.current = null;
    } });
  };
  const openDialog = () => { start.reset(); setDialogOpen(true); };
  return { batches, start, active, selectedIds: eligibleIds, selectedTopics, dialogOpen, setDialogOpen, message, select, toggle, submit, openDialog };
}
