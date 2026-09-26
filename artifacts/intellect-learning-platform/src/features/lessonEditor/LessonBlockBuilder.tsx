import { useEffect, useMemo, useState } from 'react';
import { blockSourceLabel } from '@/features/textbooks/lessonSource';
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ChevronUp, Eye, GripVertical, Loader2, Pencil, Plus, Search, Trash2, WandSparkles, X } from 'lucide-react';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { componentDemos } from '@/features/componentCatalog/demos';
import { lessonEditorInvalidationKeys } from './workflow';
import { useComponents, useUpdateLessonBlocks, type Block, type ComponentRegistryEntry, type GeneratedLesson } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import BlockMediaGenerator, { MEDIA_CAPABLE_COMPONENTS } from './BlockMediaGenerator';
import { getEducationalVideoStatus } from '@/lib/api';
import { replaceGeneratedMediaJob } from './mediaPlacement';

type BuilderItem = { id: string; block: Block };

export default function LessonBlockBuilder({ lesson, topicId, onUnsavedChange }: { lesson: GeneratedLesson; topicId: number; onUnsavedChange?: (value: boolean) => void }) {
  const [items, setItems] = useState<BuilderItem[]>(() => toItems(lesson.blocks));
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [addAfter, setAddAfter] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ index: number; block: Block } | null>(null);
  const [mediaBlockIndex, setMediaBlockIndex] = useState<number | null>(null);
  const [unsaved, setUnsaved] = useState(false);
  const [query, setQuery] = useState('');
  const componentsQuery = useComponents();
  const updateMutation = useUpdateLessonBlocks();
  const queryClient = useQueryClient();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  useEffect(() => { onUnsavedChange?.(unsaved); }, [unsaved, onUnsavedChange]);
  useEffect(() => { if (!unsaved) setItems(toItems(lesson.blocks)); }, [lesson.blocks, unsaved]);

  const pendingVideoJobs = useMemo(() => collectPendingVideoJobs(lesson.blocks), [lesson.blocks]);
  useEffect(() => {
    if (pendingVideoJobs.length === 0 || updateMutation.isPending || unsaved) return;
    const timer = window.setTimeout(async () => {
      let nextBlocks = lesson.blocks;
      let changed = false;
      for (const jobId of pendingVideoJobs) {
        try {
          const job = await getEducationalVideoStatus(jobId);
          if (job.content_url) {
            nextBlocks = replaceGeneratedMediaJob(nextBlocks, jobId, {
              kind: 'video', url: job.content_url, alt_text: 'Учебное видео',
              caption: 'Контекстное объяснение', job_id: job.id,
              generation_id: job.generation_id, model: job.model,
            });
            changed = true;
          }
        } catch {
          // A later polling cycle can retry transient provider errors.
        }
      }
      if (changed) {
        await updateMutation.mutateAsync({ lesson_id: lesson.id, blocks: nextBlocks });
        await Promise.all(lessonEditorInvalidationKeys(topicId).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
      }
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [lesson.blocks, lesson.id, pendingVideoJobs, queryClient, topicId, updateMutation.isPending, unsaved]);

  const persist = async (next: BuilderItem[]) => {
    setItems(next);
    setUnsaved(true);
    try {
      const saved = await updateMutation.mutateAsync({ lesson_id: lesson.id, blocks: next.map((item) => item.block) });
      queryClient.setQueryData(['lesson', topicId, 'teacher', undefined], saved);
      setUnsaved(false);
      await Promise.all(lessonEditorInvalidationKeys(topicId).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    } catch { /* Preserve local blocks and expose retry below. */ }
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (updateMutation.isPending || !over || active.id === over.id) return;
    const oldIndex = items.findIndex((item) => item.id === active.id);
    const newIndex = items.findIndex((item) => item.id === over.id);
    void persist(arrayMove(items, oldIndex, newIndex));
  };

  const remove = (index: number) => {
    if (!window.confirm('Удалить этот блок из урока?')) return;
    void persist(items.filter((_, itemIndex) => itemIndex !== index));
  };

  const addBlock = (entry: ComponentRegistryEntry) => {
    const demo = componentDemos[entry.id]?.block;
    if (!demo) return;
    const item = { id: makeId(), block: cloneBlock(demo) };
    const index = addAfter === null ? items.length : addAfter + 1;
    const next = [...items];
    next.splice(index, 0, item);
    setAddAfter(null);
    setQuery('');
    void persist(next);
  };

  const saveEditedBlock = () => {
    if (!editing) return;
    const next = [...items];
    next[editing.index] = { ...next[editing.index], block: editing.block };
    setEditing(null);
    void persist(next);
  };

  const subject = String(lesson.lesson_metadata?.subject_name || '');
  const available = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const subjectCode = subjectSlug(subject);
    return (componentsQuery.data || [])
      .filter((entry) => entry.id !== 'generated-media')
      .filter((entry) => !needle || `${entry.purpose} ${entry.id} ${categoryLabel(entry.category)}`.toLowerCase().includes(needle))
      .sort((a, b) => Number(b.subjects.includes(subjectCode)) - Number(a.subjects.includes(subjectCode)));
  }, [componentsQuery.data, query, subject]);

  return (
    <section data-testid="lesson-block-builder" className="mt-8">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground">Конструктор урока</h2>
          <p className="mt-1 text-sm text-muted-foreground">Перетаскивайте блоки за маркер. Изменения сохраняются автоматически.</p>
        </div>
        <button
          type="button"
          disabled={updateMutation.isPending} onClick={() => setAddAfter(items.length - 1)}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 text-sm font-bold text-foreground hover:bg-muted"
        >
          <Plus className="h-4 w-4" /> Добавить блок
        </button>
      </div>

      {updateMutation.isPending && (
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Сохраняется…</div>
      )}
      {updateMutation.error && (
        <div role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">Не удалось сохранить. Ваши изменения сохранены на экране. {(updateMutation.error as Error).message} <button type="button" onClick={() => void persist(items)} className="underline font-bold">Повторить сохранение</button></div>
      )}

      {!unsaved && updateMutation.isSuccess && <p role="status" className="mb-3 text-sm text-green-700">Сохранено</p>}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={items.map((item) => item.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {items.map((item, index) => (
              <SortableBlock
                key={item.id}
                item={item}
                index={index}
                expanded={expandedId === item.id}
                disabled={updateMutation.isPending}
                onToggle={() => setExpandedId((current) => current === item.id ? null : item.id)}
                onAdd={() => setAddAfter(index)}
                onEdit={() => setEditing({ index, block: cloneBlock(item.block) })}
                onMedia={!unsaved && MEDIA_CAPABLE_COMPONENTS.has(item.block.component) ? () => setMediaBlockIndex(index) : undefined}
                onRemove={() => remove(index)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {addAfter !== null && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="Добавить блок">
          <div className="max-h-[82vh] w-full max-w-3xl overflow-hidden rounded-t-lg border border-border bg-background shadow-2xl sm:rounded-lg">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div>
                <h3 className="font-bold text-foreground">Добавить учебный блок</h3>
                <p className="text-xs text-muted-foreground">Подходящие для предмета «{subject || 'текущий'}» показаны первыми.</p>
              </div>
              <button type="button" onClick={() => setAddAfter(null)} aria-label="Закрыть" className="flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted"><X className="h-5 w-5" /></button>
            </div>
            <div className="border-b border-border p-4">
              <label className="flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-3">
                <Search className="h-4 w-4 text-muted-foreground" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти объяснение, практику, схему..." className="min-w-0 flex-1 bg-transparent text-sm outline-none" autoFocus />
              </label>
            </div>
            <div className="grid max-h-[58vh] gap-2 overflow-y-auto p-4 sm:grid-cols-2">
              {available.map((entry) => (
                <button key={entry.id} type="button" onClick={() => addBlock(entry)} className="min-h-24 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary hover:bg-primary/5">
                  <span className="text-xs font-bold uppercase text-primary">{categoryLabel(entry.category)}</span>
                  <span className="mt-1 block font-bold text-foreground">{entry.purpose}</span>
                  <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">{componentDemos[entry.id]?.usage || entry.rendering_notes}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {editing && (
        <BlockEditorDialog
          block={editing.block}
          onChange={(block) => setEditing((current) => current ? { ...current, block } : null)}
          onClose={() => setEditing(null)}
          onSave={saveEditedBlock}
        />
      )}
      {mediaBlockIndex !== null && (
        <BlockMediaGenerator
          lesson={lesson}
          topicId={topicId}
          blockIndex={mediaBlockIndex}
          onClose={() => setMediaBlockIndex(null)}
        />
      )}
    </section>
  );
}

function SortableBlock({ item, index, expanded, disabled, onToggle, onAdd, onEdit, onMedia, onRemove }: {
  item: BuilderItem; index: number; expanded: boolean; disabled: boolean;
  onToggle: () => void; onAdd: () => void; onEdit: () => void; onMedia?: () => void; onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id, disabled });
  const style = { transform: CSS.Transform.toString(transform), transition };
  return (
    <div ref={setNodeRef} style={style} className={`overflow-hidden rounded-lg border bg-background ${isDragging ? 'z-20 border-primary shadow-lg' : 'border-border'}`}>
      <div className="flex min-h-14 items-center gap-2 px-2 sm:px-3">
        <button type="button" {...attributes} {...listeners} aria-label={`Переместить блок ${index + 1}`} className="flex h-10 w-8 shrink-0 cursor-grab items-center justify-center text-muted-foreground hover:text-foreground active:cursor-grabbing"><GripVertical className="h-5 w-5" /></button>
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-bold text-muted-foreground">{index + 1}</span>
        <button type="button" onClick={onToggle} className="min-w-0 flex-1 py-3 text-left">
          <span className="block truncate text-sm font-bold text-foreground">{blockTitle(item.block)}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {componentLabel(item.block.component)}
            {blockSourceLabel(item.block.content) && <span className="text-emerald-700"> · {blockSourceLabel(item.block.content)}</span>}
          </span>
        </button>
        <button type="button" onClick={onToggle} aria-label="Предпросмотр" title="Предпросмотр" className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">{expanded ? <ChevronUp className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
        {onMedia && <button type="button" disabled={disabled} onClick={onMedia} aria-label="Создать AI-медиа для блока" title="Создать AI-медиа" className="flex h-9 w-9 items-center justify-center rounded-md text-primary hover:bg-primary/10"><WandSparkles className="h-4 w-4" /></button>}
        <button type="button" disabled={disabled} onClick={onEdit} aria-label="Редактировать блок" title="Редактировать" className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"><Pencil className="h-4 w-4" /></button>
        <button type="button" disabled={disabled} onClick={onAdd} aria-label="Добавить блок после" title="Добавить после" className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"><Plus className="h-4 w-4" /></button>
        <button type="button" disabled={disabled} onClick={onRemove} aria-label="Удалить блок" title="Удалить" className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
      </div>
      {expanded && (
        <div className="border-t border-border bg-muted/10 p-3 sm:p-5">
          <div className="pointer-events-none origin-top scale-[0.98]"><BlockRenderer blocks={[item.block]} /></div>
        </div>
      )}
    </div>
  );
}

function BlockEditorDialog({ block, onChange, onClose, onSave }: {
  block: Block; onChange: (block: Block) => void; onClose: () => void; onSave: () => void;
}) {
  const updateContent = (path: Array<string | number>, value: unknown) => {
    onChange({ ...block, content: setAtPath(block.content, path, value) as Record<string, unknown> });
  };
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="Редактировать блок">
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-lg border border-border bg-background shadow-2xl sm:rounded-lg">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h3 className="font-bold text-foreground">{blockTitle(block)}</h3>
            <p className="text-xs text-muted-foreground">{componentLabel(block.component)}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Закрыть редактор" className="flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {Object.entries(block.content)
            .filter(([key]) => !TECHNICAL_FIELDS.has(key))
            .map(([key, value]) => (
              <ContentField key={key} label={fieldLabel(key)} value={value} path={[key]} onChange={updateContent} />
            ))}
        </div>
        <div className="flex justify-end gap-2 border-t border-border p-4">
          <button type="button" onClick={onClose} className="h-10 rounded-lg border border-border px-4 text-sm font-bold hover:bg-muted">Отмена</button>
          <button type="button" onClick={onSave} className="h-10 rounded-lg bg-primary px-5 text-sm font-bold text-primary-foreground hover:bg-primary/90">Сохранить блок</button>
        </div>
      </div>
    </div>
  );
}

function ContentField({ label, value, path, onChange }: {
  label: string; value: unknown; path: Array<string | number>;
  onChange: (path: Array<string | number>, value: unknown) => void;
}) {
  if (typeof value === 'boolean') {
    return <label className="flex items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={value} onChange={(event) => onChange(path, event.target.checked)} className="h-4 w-4" />{label}</label>;
  }
  if (typeof value === 'number') {
    return <FieldShell label={label}><input type="number" value={value} onChange={(event) => onChange(path, Number(event.target.value))} className={inputClass} /></FieldShell>;
  }
  if (typeof value === 'string') {
    const multiline = value.length > 80 || /text|body|description|explanation|script|prompt|callout/i.test(String(path.at(-1)));
    return <FieldShell label={label}>{multiline
      ? <textarea value={value} onChange={(event) => onChange(path, event.target.value)} className={`${inputClass} min-h-24 resize-y py-2`} />
      : <input value={value} onChange={(event) => onChange(path, event.target.value)} className={inputClass} />
    }</FieldShell>;
  }
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === 'string')) {
      return <FieldShell label={`${label} (по одному на строку)`}><textarea value={value.join('\n')} onChange={(event) => onChange(path, event.target.value.split('\n').map((line) => line.trim()).filter(Boolean))} className={`${inputClass} min-h-24 resize-y py-2`} /></FieldShell>;
    }
    return (
      <fieldset className="space-y-3 border-l-2 border-border pl-4">
        <legend className="px-1 text-sm font-bold text-foreground">{label}</legend>
        {value.map((item, index) => (
          <div key={index} className="relative space-y-3 border-b border-border pb-4">
            <div className="flex items-center justify-between text-xs font-bold text-muted-foreground">
              <span>{label} {index + 1}</span>
              <button type="button" onClick={() => onChange(path, value.filter((_, itemIndex) => itemIndex !== index))} className="text-destructive">Удалить</button>
            </div>
            {item && typeof item === 'object'
              ? Object.entries(item as Record<string, unknown>).filter(([key]) => !TECHNICAL_FIELDS.has(key)).map(([key, nested]) => (
                <ContentField key={key} label={fieldLabel(key)} value={nested} path={[...path, index, key]} onChange={onChange} />
              ))
              : <ContentField label="Значение" value={item} path={[...path, index]} onChange={onChange} />}
          </div>
        ))}
        {value.length > 0 && (
          <button type="button" onClick={() => onChange(path, [...value, emptyLike(value[0])])} className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-xs font-bold hover:bg-muted"><Plus className="h-3.5 w-3.5" /> Добавить</button>
        )}
      </fieldset>
    );
  }
  if (value && typeof value === 'object') {
    return (
      <fieldset className="space-y-3 border-l-2 border-border pl-4">
        <legend className="px-1 text-sm font-bold text-foreground">{label}</legend>
        {Object.entries(value as Record<string, unknown>).filter(([key]) => !TECHNICAL_FIELDS.has(key)).map(([key, nested]) => (
          <ContentField key={key} label={fieldLabel(key)} value={nested} path={[...path, key]} onChange={onChange} />
        ))}
      </fieldset>
    );
  }
  return null;
}

function FieldShell({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-semibold text-muted-foreground"><span className="mb-1 block">{label}</span>{children}</label>;
}

const inputClass = 'min-h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none focus:border-primary';
const TECHNICAL_FIELDS = new Set(['objective_ids', 'anchor', 'prompt', 'model', 'job_id', 'generation_id', 'media_slot']);

function setAtPath(source: unknown, path: Array<string | number>, value: unknown): unknown {
  if (path.length === 0) return value;
  const [head, ...tail] = path;
  const clone: Record<string | number, unknown> | unknown[] = Array.isArray(source)
    ? [...source]
    : { ...((source && typeof source === 'object') ? source as Record<string, unknown> : {}) };
  const current = (clone as Record<string | number, unknown>)[head];
  (clone as Record<string | number, unknown>)[head] = setAtPath(current, tail, value);
  return clone;
}

function emptyLike(value: unknown): unknown {
  if (typeof value === 'string') return '';
  if (typeof value === 'number') return 0;
  if (typeof value === 'boolean') return false;
  if (Array.isArray(value)) return [];
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, emptyLike(item)]));
  return '';
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    title: 'Заголовок', heading: 'Заголовок', text: 'Объяснение', body: 'Содержание', term: 'Термин', definition: 'Определение',
    example: 'Пример', non_example: 'Контрпример', visual_hint: 'Визуальная подсказка', key_concepts: 'Ключевые понятия', callout: 'Акцент',
    question: 'Вопрос', problem: 'Задание', task: 'Задание', options: 'Варианты ответа', correct_answer: 'Правильный ответ',
    explanation: 'Обратная связь', hints: 'Подсказки', slides: 'Слайды', learning_point: 'Учебный смысл', steps: 'Шаги',
    description: 'Описание', math: 'Формула', events: 'События', date: 'Дата', label: 'Название', final_answer: 'Итоговый ответ',
    type: 'Тип взаимодействия', avatar_script: 'Реплика помощника', evidence_stage: 'Этап обучения',
  };
  return labels[key] || key.replaceAll('_', ' ');
}

function collectPendingVideoJobs(blocks: Block[]): string[] {
  const ids = new Set<string>();
  blocks.forEach((block) => {
    if (block.component === 'GeneratedMedia' && block.content.media_kind === 'video' && !block.content.url && typeof block.content.job_id === 'string') {
      ids.add(block.content.job_id);
    }
    if (block.component === 'Presentation' && Array.isArray(block.content.slides)) {
      block.content.slides.forEach((rawSlide) => {
        if (!rawSlide || typeof rawSlide !== 'object') return;
        const media = (rawSlide as Record<string, unknown>).media;
        if (!media || typeof media !== 'object') return;
        const value = media as Record<string, unknown>;
        if (value.kind === 'video' && !value.url && typeof value.job_id === 'string') ids.add(value.job_id);
      });
    }
  });
  return Array.from(ids).sort();
}

function toItems(blocks: Block[] = []): BuilderItem[] {
  return blocks.map((block) => ({ id: makeId(), block }));
}

function makeId(): string {
  return globalThis.crypto?.randomUUID?.() || `block-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function cloneBlock(block: Block): Block {
  return JSON.parse(JSON.stringify(block)) as Block;
}

function blockTitle(block: Block): string {
  const content = block.content || {};
  for (const key of ['title', 'heading', 'term', 'question', 'problem', 'prompt', 'task']) {
    if (typeof content[key] === 'string' && content[key]) return String(content[key]);
  }
  return componentLabel(block.component);
}

function componentLabel(component: string): string {
  const labels: Record<string, string> = {
    ShortExplanation: 'Объяснение', KeyConcept: 'Ключевое понятие', WorkedExample: 'Разбор примера',
    GuidedPractice: 'Практика с поддержкой', IndependentProblem: 'Самостоятельное задание', RetrievalCheck: 'Быстрая проверка',
    Presentation: 'Презентация', GeneratedMedia: 'AI-медиа', MasteryCheck: 'Итоговая проверка', Reflection: 'Рефлексия',
    MindMap: 'Карта понятий', Timeline: 'Лента времени', SortAndClassify: 'Сортировка', ProcessBuilder: 'Сборка процесса',
    ArgumentMap: 'Карта аргументов', BranchingScenario: 'Сценарий решений', MisconceptionDebugger: 'Разбор ошибки',
    PredictionLab: 'Лаборатория прогноза', DataInvestigation: 'Исследование данных', PhysicsSandbox: 'Физическая модель',
    HotspotInvestigation: 'Исследование изображения', CodeBlocksLab: 'Блоковое программирование', ChronologyLine: 'Лента событий', Illustration: 'Иллюстрация',
  };
  return labels[component] || component;
}

function categoryLabel(category: string): string {
  return ({ explain: 'Объяснение', model: 'Пример', practice: 'Практика', assess: 'Проверка', represent: 'Визуализация', interact: 'Интерактив', communicate: 'Рассуждение', reflect: 'Рефлексия', media: 'Медиа' } as Record<string, string>)[category] || category;
}

function subjectSlug(subject: string): string {
  const value = subject.toLowerCase();
  if (value.includes('математ') || value.includes('алгебр') || value.includes('геометр')) return 'math';
  if (value.includes('литератур') || value.includes('язык')) return 'literature';
  if (value.includes('физик')) return 'physics';
  if (value.includes('биолог')) return 'biology';
  if (value.includes('хими')) return 'chemistry';
  if (value.includes('истори')) return 'history';
  if (value.includes('географ')) return 'geography';
  if (value.includes('информат')) return 'informatics';
  return 'general';
}
