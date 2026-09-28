import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, Loader2, Plus, Sparkles } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import type { ComponentRegistryEntry, GeneratedLesson } from '@/lib/api';
import {
  componentContextKey, getLessonComponentContext, insertLessonComponent, prepareLessonComponent,
  type PreparedLessonComponent,
} from '@/lib/api/lessonComponents';
import { componentDemos } from '@/features/componentCatalog/demos';

type Props = {
  lessonId: number;
  afterIndex: number;
  components: ComponentRegistryEntry[];
  initialComponent?: string;
  onInserted: (lesson: GeneratedLesson) => void;
  onClose: () => void;
};

const fieldClass = 'min-h-11 w-full min-w-0 rounded-xl border border-border bg-background px-3 text-base disabled:opacity-60';

export default function PrepareComponentDialog({ lessonId, afterIndex, components, initialComponent, onInserted, onClose }: Props) {
  const context = useQuery({
    queryKey: componentContextKey(lessonId), queryFn: () => getLessonComponentContext(lessonId),
    staleTime: 0, retry: false, refetchOnWindowFocus: false,
  });
  const [selectedComponent, setSelectedComponent] = useState(initialComponent ?? 'worked-example');
  const [selectedObjective, setSelectedObjective] = useState('');
  const [selectedSection, setSelectedSection] = useState('');
  const [selectedItem, setSelectedItem] = useState('');
  const [prepared, setPrepared] = useState<PreparedLessonComponent | null>(null);
  const [busy, setBusy] = useState<'prepare' | 'insert' | null>(null);
  const [error, setError] = useState('');
  const [paidConsent, setPaidConsent] = useState(false);
  const requestId = useRef('');
  const inFlight = useRef(false);
  const available = components.filter((entry) => {
    const name = componentDemos[entry.id]?.block.component;
    return name && name !== 'GeneratedMedia' && (!context.data?.supported_components || context.data.supported_components.includes(name));
  });
  const entry = available.find((item) => item.id === selectedComponent) ?? available[0];
  const objective = context.data?.objectives.find((item) => item.id === selectedObjective) ?? context.data?.objectives[0];
  const source = context.data?.sources.find((item) => String(item.section_id) === selectedSection) ?? context.data?.sources[0];
  const sourceItem = source?.items.find((item) => String(item.id) === selectedItem);
  const canPrepare = Boolean(entry && objective && source && paidConsent && !context.isFetching && !context.isError && !context.data?.reason);

  const prepare = async () => {
    if (!canPrepare || !entry || !objective || !source || !context.data || inFlight.current) return;
    inFlight.current = true;
    setBusy('prepare'); setError(''); setPrepared(null);
    try {
      const result = await prepareLessonComponent(lessonId, {
        component: componentDemos[entry.id].block.component,
        objective_id: objective.id, after_index: afterIndex, base_revision: context.data.revision,
        source_section_id: source.section_id, source_item_id: sourceItem?.id ?? null,
      });
      requestId.current = crypto.randomUUID();
      setPrepared(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Не удалось подготовить блок. Попробуйте снова.');
    } finally { inFlight.current = false; setBusy(null); }
  };

  const insert = async () => {
    if (!prepared || inFlight.current) return;
    inFlight.current = true;
    setBusy('insert'); setError('');
    try {
      const lesson = await insertLessonComponent(lessonId, {
        block: prepared.block, base_revision: prepared.base_revision,
        context_fingerprint: prepared.context_fingerprint, after_index: afterIndex, request_id: requestId.current,
      });
      onInserted(lesson);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Не удалось вставить блок. Предпросмотр сохранён.');
    } finally { inFlight.current = false; setBusy(null); }
  };

  const close = () => { if (!inFlight.current) onClose(); };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) close(); }}>
      <DialogContent className="max-h-[92vh] w-[calc(100vw-1rem)] max-w-4xl overflow-y-auto p-4 sm:p-6" aria-busy={Boolean(busy)}>
        <DialogHeader className="pr-7 text-left">
          <DialogTitle>Добавить блок по теме урока</DialogTitle>
          <DialogDescription>Выберите цель и материал учебника. Готовый блок сначала появится для просмотра.</DialogDescription>
        </DialogHeader>
        {context.isPending && <p role="status" className="flex items-center gap-2 py-8 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Загружаем цели и параграфы…</p>}
        {context.isError && <div role="alert" className="rounded-xl bg-destructive/10 p-4 text-sm text-destructive">{context.error.message}<button type="button" onClick={() => void context.refetch()} className="ml-2 underline">Повторить</button></div>}
        {context.data && !prepared && (
          <div className="space-y-4">
            {(context.data.reason || !source || !objective) && (
              <div role="status" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
                {context.data.reason || (!source ? 'Привяжите тему к распознанному параграфу учебника.' : 'Добавьте учебную цель в КТП этой темы.')}
              </div>
            )}
            <fieldset disabled={Boolean(busy)} className="grid min-w-0 gap-4 sm:grid-cols-2">
              <label className="min-w-0 space-y-1 text-sm font-semibold sm:col-span-2">Цель КТП
                <select aria-label="Цель КТП" className={fieldClass} value={objective?.id ?? ''} onChange={(event) => setSelectedObjective(event.target.value)}>
                  {!objective && <option value="">Нет целей</option>}
                  {context.data.objectives.map((item) => <option key={item.id} value={item.id}>{item.text}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-1 text-sm font-semibold">Параграф
                <select aria-label="Параграф" className={fieldClass} value={source ? String(source.section_id) : ''} onChange={(event) => { setSelectedSection(event.target.value); setSelectedItem(''); }}>
                  {!source && <option value="">Нет подтверждённого параграфа</option>}
                  {context.data.sources.map((item) => <option key={item.section_id} value={item.section_id}>{item.title}{item.page_from != null ? ` · стр. ${item.page_from}` : ''}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-1 text-sm font-semibold">Материал
                <select aria-label="Материал учебника" className={fieldClass} value={selectedItem} onChange={(event) => setSelectedItem(event.target.value)}>
                  <option value="">По содержанию параграфа</option>
                  {source?.items.map((item) => <option key={item.id} value={item.id}>{item.label || `Материал №${item.id}`}{item.page != null ? ` · стр. ${item.page}` : ''}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-1 text-sm font-semibold sm:col-span-2">Формат блока
                <select aria-label="Формат блока" className={fieldClass} value={entry?.id ?? ''} onChange={(event) => setSelectedComponent(event.target.value)}>
                  {available.map((item) => <option key={item.id} value={item.id}>{item.purpose}</option>)}
                </select>
                {entry && <p className="font-normal text-muted-foreground">{componentDemos[entry.id]?.usage}</p>}
              </label>
              <label className="flex items-start gap-3 rounded-xl bg-muted/40 p-3 text-sm sm:col-span-2">
                <input type="checkbox" checked={paidConsent} onChange={(event) => setPaidConsent(event.target.checked)} className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Разрешаю платную AI-генерацию одного блока по выбранному материалу.</span>
              </label>
            </fieldset>
            <button type="button" disabled={!canPrepare || Boolean(busy)} onClick={() => void prepare()} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground disabled:opacity-50">
              {busy === 'prepare' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {busy === 'prepare' ? 'Подготавливаем по учебнику…' : 'Подготовить по учебнику'}
            </button>
          </div>
        )}
        {prepared && (
          <div className="min-w-0 space-y-4">
            <div className="flex items-start gap-2 rounded-xl bg-emerald-500/10 p-3 text-sm"><BookOpen className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="font-semibold">{prepared.source_label}</p><p className="mt-1 text-muted-foreground">Цель: {objective?.text}</p></div></div>
            {prepared.warnings.map((warning, index) => <p key={index} className="rounded-xl bg-amber-500/10 p-3 text-sm">{warning}</p>)}
            <div className="min-w-0 rounded-xl border border-border p-2 sm:p-4"><BlockRenderer blocks={[prepared.block]} /></div>
            <p className="text-xs text-muted-foreground">Это предпросмотр. После вставки содержание можно отредактировать в черновике.</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={Boolean(busy)} onClick={() => void insert()} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground disabled:opacity-50">{busy === 'insert' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Вставить в урок</button>
              <button type="button" disabled={Boolean(busy)} onClick={() => { setPrepared(null); setPaidConsent(false); setError(''); void context.refetch(); }} className="min-h-11 rounded-xl border border-border px-4 text-sm">Изменить выбор</button>
            </div>
          </div>
        )}
        {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      </DialogContent>
    </Dialog>
  );
}
