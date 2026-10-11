import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import ModelPicker, { useModelChoice } from '@/features/lessonEditor/ModelPicker';
import { useAiModels, type Topic } from '@/lib/api';
import { LANGUAGE_OPTIONS, type InstructionLanguage, isInstructionLanguage } from '@/lib/languages';
import { hasDraftMaterials } from './batchGenerationModel';

export type BatchOptions = { model?: string; contentLanguage?: InstructionLanguage; replaceDrafts: boolean };
export function BatchGenerationDialog({ topics, onClose, onSubmit, pending, error }: {
  topics: Topic[]; onClose: () => void; onSubmit: (options: BatchOptions) => void;
  pending: boolean; error?: string;
}) {
  const models = useAiModels();
  const choice = useModelChoice(models.data?.lesson, 'intellect:lesson-model');
  const [language, setLanguage] = useState('program');
  const [replace, setReplace] = useState(false);
  const existing = topics.filter(hasDraftMaterials);
  return <Dialog open onOpenChange={open => { if (!open && !pending) onClose(); }}><DialogContent>
    <DialogTitle>Подготовка материалов · {topics.length}</DialogTitle>
    <DialogDescription>Каждый урок — отдельная генерация ИИ. Сервер подготовит черновики в фоне; их нужно проверить перед публикацией.</DialogDescription>
    <ol className="max-h-48 list-decimal space-y-2 overflow-y-auto pl-5 text-sm">{topics.map(topic => <li key={topic.id}>{topic.ktp_number ? `${topic.ktp_number}. ` : ''}{topic.name}</li>)}</ol>
    <ModelPicker label="Модель для всех выбранных уроков" group={models.data?.lesson} choice={choice} disabled={pending} loadError={models.isError} />
    <label className="text-sm font-semibold">Язык материалов<select aria-label="Язык материалов" disabled={pending} value={language} onChange={event => setLanguage(event.target.value)} className="mt-1 h-10 w-full rounded-lg border bg-card px-3"><option value="program">Язык программы</option>{LANGUAGE_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
    {existing.length > 0 && <label className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"><input type="checkbox" checked={replace} disabled={pending} onChange={event => setReplace(event.target.checked)} />Заменить материалы {existing.length} выбранных черновиков. Правки в этих черновиках будут заменены после успешной генерации.</label>}
    <p className="text-sm text-muted-foreground">Можно закрыть страницу после запуска. Очередь и результаты останутся в программе.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex justify-end gap-2"><button disabled={pending} onClick={onClose} className="rounded-lg border px-4 py-2">Отмена</button><button disabled={pending || !topics.length || (existing.length > 0 && !replace)} onClick={() => onSubmit({ model: choice.requestModel, contentLanguage: isInstructionLanguage(language) ? language : undefined, replaceDrafts: replace })} className="rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground disabled:opacity-50">{pending ? 'Добавляем в очередь…' : `Запустить подготовку (${topics.length})`}</button></div>
  </DialogContent></Dialog>;
}
