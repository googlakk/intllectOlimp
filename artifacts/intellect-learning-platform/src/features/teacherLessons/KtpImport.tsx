import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'wouter';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileUp,
  Loader2,
  Plus,
  Trash2,
  UploadCloud,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { parseKtpFile, uploadKtp, type KtpDraft, type KtpTopicDraft } from '@/lib/api';
import { emptySection, emptyTopic, normalizeKtpDraft, summarizeKtpDraft, validateKtpDraft } from './ktpDraft';
import { isInstructionLanguage, LANGUAGE_OPTIONS } from '@/lib/languages';

const TEMPLATE_URL = '/templates/ktp-template-2026.xlsx';
const SUBJECTS = [
  'Алгебра', 'Биология', 'Всемирная история', 'География', 'Геометрия', 'Информатика',
  'История Кыргызстана', 'Кыргызская литература', 'Кыргызский язык', 'Математика', 'Русская литература',
  'Русский язык', 'Физика', 'Химия', 'Человек и общество', 'Английский язык', 'Технология', 'Физическая культура',
];

type ImportStage = 'upload' | 'parsing' | 'review' | 'saving' | 'success';

function fieldClass() {
  return 'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10';
}

function KtpImportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<ImportStage>('upload');
  const [draft, setDraft] = useState<KtpDraft | null>(null);
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setDragging] = useState(false);

  const reset = () => {
    setStage('upload');
    setDraft(null);
    setFileName('');
    setError(null);
    setDragging(false);
    if (inputRef.current) inputRef.current.value = '';
  };

  const setOpen = (next: boolean) => {
    onOpenChange(next);
    if (!next) window.setTimeout(reset, 200);
  };

  const parseFile = async (file?: File) => {
    if (!file) return;
    setFileName(file.name);
    setError(null);
    setStage('parsing');
    try {
      const parsed = await parseKtpFile(file);
      setDraft(parsed);
      setStage('review');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось прочитать КТП');
      setStage('upload');
    } finally {
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void parseFile(event.dataTransfer.files?.[0]);
  };

  const updateSection = (sectionIndex: number, updater: (section: KtpDraft['sections'][number]) => KtpDraft['sections'][number]) => {
    setDraft((current) => current ? {
      ...current,
      sections: current.sections.map((section, index) => index === sectionIndex ? updater(section) : section),
    } : current);
  };

  const updateTopic = (sectionIndex: number, topicIndex: number, field: keyof KtpTopicDraft, value: string | number) => {
    updateSection(sectionIndex, (section) => ({
      ...section,
      topics: section.topics.map((topic, index) => index === topicIndex ? { ...topic, [field]: value } : topic),
    }));
  };

  const save = async () => {
    if (!draft) return;
    const normalized = normalizeKtpDraft(draft);
    const validationError = validateKtpDraft(normalized);
    if (validationError) {
      setError(validationError);
      return;
    }
    setDraft(normalized);
    setError(null);
    setStage('saving');
    try {
      await uploadKtp(normalized);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['subjects'] }),
        queryClient.invalidateQueries({ queryKey: ['sections'] }),
        queryClient.invalidateQueries({ queryKey: ['topics'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] }),
      ]);
      setStage('success');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить КТП');
      setStage('review');
    }
  };

  const summary = draft ? summarizeKtpDraft(draft) : null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-5xl gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-6 py-5 pr-14">
          <DialogTitle className="text-xl">Импорт календарно-тематического плана</DialogTitle>
          <DialogDescription>Проверьте структуру до добавления тем в курс.</DialogDescription>
        </DialogHeader>

        {(stage === 'upload' || stage === 'parsing') && (
          <div className="space-y-5 p-6">
            <div
              className={`flex min-h-64 flex-col items-center justify-center border-2 border-dashed px-6 py-10 text-center transition-colors ${isDragging ? 'border-primary bg-primary/5' : 'border-border bg-muted/20'}`}
              onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              {stage === 'parsing' ? <Loader2 className="mb-5 h-10 w-10 animate-spin text-primary" /> : <UploadCloud className="mb-5 h-10 w-10 text-primary" />}
              <p className="text-lg font-bold text-foreground">{stage === 'parsing' ? 'Разбираем структуру КТП' : 'Перетащите файл сюда'}</p>
              <p className="mt-2 max-w-lg text-sm text-muted-foreground">
                {stage === 'parsing' ? fileName : 'Форматы: XLSX по нашему шаблону, DOCX или PDF с таблицей. До 10 МБ.'}
              </p>
              <input ref={inputRef} type="file" className="hidden" accept=".xlsx,.docx,.pdf" onChange={(event: ChangeEvent<HTMLInputElement>) => void parseFile(event.target.files?.[0])} />
              {stage === 'upload' && (
                <button type="button" onClick={() => inputRef.current?.click()} className="mt-6 inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:bg-primary/90">
                  <FileUp className="h-4 w-4" /> Выбрать файл
                </button>
              )}
            </div>
            <div className="flex flex-col justify-between gap-3 border-t border-border pt-5 sm:flex-row sm:items-center">
              <div>
                <p className="font-bold text-foreground">Нет готового файла?</p>
                <p className="text-sm text-muted-foreground">Шаблон подходит для любого предмета 7–10 классов.</p>
              </div>
              <a href={TEMPLATE_URL} download className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-bold text-foreground hover:bg-muted">
                <Download className="h-4 w-4" /> Скачать шаблон
              </a>
            </div>
            {error && <p role="alert" className="rounded-lg bg-destructive/10 px-4 py-3 text-sm font-semibold text-destructive">{error}</p>}
          </div>
        )}

        {(stage === 'review' || stage === 'saving') && draft && summary && (
          <>
            <div className="max-h-[calc(85vh-150px)] space-y-6 overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  ['Разделов', summary.sections], ['Тем', summary.topics], ['Часов', summary.hours], ['Без целей', summary.topicsWithoutObjectives],
                ].map(([label, value]) => (
                  <div key={label} className="border-l-2 border-primary px-3 py-1">
                    <div className="text-2xl font-bold text-foreground">{value}</div>
                    <div className="text-xs font-semibold text-muted-foreground">{label}</div>
                  </div>
                ))}
              </div>

              <section className="space-y-3 border-y border-border py-5">
                <h3 className="font-bold text-foreground">Общие данные</h3>
                <div className="grid gap-4 md:grid-cols-4">
                  <label className="md:col-span-2 text-sm font-semibold text-foreground">Предмет
                    <input list="ktp-subjects" value={draft.subject_name} onChange={(event) => setDraft({ ...draft, subject_name: event.target.value })} className={`${fieldClass()} mt-1.5`} />
                    <datalist id="ktp-subjects">{SUBJECTS.map((subject) => <option value={subject} key={subject} />)}</datalist>
                  </label>
                  <label className="text-sm font-semibold text-foreground">Класс
                    <select value={draft.grade} onChange={(event) => setDraft({ ...draft, grade: Number(event.target.value) })} className={`${fieldClass()} mt-1.5`}>
                      {[7, 8, 9, 10].map((grade) => <option value={grade} key={grade}>{grade}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-foreground">Язык
                    <select value={draft.instruction_language} onChange={(event) => { if (isInstructionLanguage(event.target.value)) setDraft({ ...draft, instruction_language: event.target.value }); }} className={`${fieldClass()} mt-1.5`}>
                      {LANGUAGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-foreground">Часов в неделю
                    <input type="number" min="0.5" step="0.5" value={draft.hours_per_week} onChange={(event) => setDraft({ ...draft, hours_per_week: Number(event.target.value) })} className={`${fieldClass()} mt-1.5`} />
                  </label>
                  <div className="text-sm font-semibold text-foreground">Исходный файл
                    <div className="mt-1.5 flex h-10 items-center gap-2 truncate rounded-lg bg-muted px-3 font-medium text-muted-foreground"><FileSpreadsheet className="h-4 w-4 shrink-0" /> {fileName}</div>
                  </div>
                </div>
              </section>

              {(draft.warnings?.length || summary.topicsWithoutObjectives > 0) ? (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900">
                  <div className="flex items-center gap-2 font-bold"><AlertTriangle className="h-4 w-4" /> Проверьте перед импортом</div>
                  <ul className="mt-2 space-y-1 text-sm">
                    {summary.topicsWithoutObjectives > 0 && <li>{summary.topicsWithoutObjectives} тем без целей обучения.</li>}
                    {draft.warnings?.slice(0, 5).map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                </div>
              ) : null}

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-4">
                  <div><h3 className="font-bold text-foreground">Структура КТП</h3><p className="text-sm text-muted-foreground">Откройте раздел, чтобы исправить темы.</p></div>
                  <button type="button" onClick={() => setDraft({ ...draft, sections: [...draft.sections, emptySection(draft.sections.length + 1)] })} className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-bold hover:bg-muted"><Plus className="h-4 w-4" /> Раздел</button>
                </div>
                {draft.sections.map((section, sectionIndex) => (
                  <details key={`${section.name}-${sectionIndex}`} className="group border-y border-border" open={sectionIndex === 0}>
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4">
                      <div className="min-w-0"><p className="truncate font-bold text-foreground">{section.name || 'Раздел без названия'}</p><p className="text-sm text-muted-foreground">{section.topics.length} тем · {section.topics.reduce((sum, topic) => sum + Number(topic.hours || 0), 0)} ч.</p></div>
                      <span className="text-sm font-bold text-primary group-open:hidden">Открыть</span><span className="hidden text-sm font-bold text-primary group-open:inline">Скрыть</span>
                    </summary>
                    <div className="space-y-4 pb-5">
                      <div className="flex gap-2">
                        <input aria-label="Название раздела" value={section.name} onChange={(event) => updateSection(sectionIndex, (current) => ({ ...current, name: event.target.value }))} className={fieldClass()} />
                        <button type="button" title="Удалить раздел" onClick={() => setDraft({ ...draft, sections: draft.sections.filter((_, index) => index !== sectionIndex) })} className="rounded-lg border border-border p-2 text-muted-foreground hover:border-destructive/30 hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                      </div>
                      {section.topics.map((topic, topicIndex) => (
                        <div key={`${topic.ktp_number}-${topicIndex}`} className="grid gap-3 border-l-2 border-border pl-4 md:grid-cols-12">
                          <label className="text-xs font-semibold text-muted-foreground md:col-span-1">№<input value={topic.ktp_number} onChange={(event) => updateTopic(sectionIndex, topicIndex, 'ktp_number', event.target.value)} className={`${fieldClass()} mt-1`} /></label>
                          <label className="text-xs font-semibold text-muted-foreground md:col-span-5">Тема<input value={topic.name} onChange={(event) => updateTopic(sectionIndex, topicIndex, 'name', event.target.value)} className={`${fieldClass()} mt-1`} /></label>
                          <label className="text-xs font-semibold text-muted-foreground md:col-span-1">Часы<input type="number" min="1" value={topic.hours} onChange={(event) => updateTopic(sectionIndex, topicIndex, 'hours', Number(event.target.value))} className={`${fieldClass()} mt-1`} /></label>
                          <label className="text-xs font-semibold text-muted-foreground md:col-span-3">Тип<select value={topic.lesson_type} onChange={(event) => updateTopic(sectionIndex, topicIndex, 'lesson_type', event.target.value)} className={`${fieldClass()} mt-1`}><option value="study">Изучение</option><option value="review">Повторение</option><option value="reflection">Разбор ошибок</option><option value="assessment">Контроль</option><option value="project">Проект</option></select></label>
                          <button type="button" title="Удалить тему" onClick={() => updateSection(sectionIndex, (current) => ({ ...current, topics: current.topics.filter((_, index) => index !== topicIndex) }))} className="mt-5 h-10 rounded-lg border border-border text-muted-foreground hover:text-destructive md:col-span-2"><Trash2 className="mx-auto h-4 w-4" /></button>
                          <label className="text-xs font-semibold text-muted-foreground md:col-span-12">Цели обучения<textarea rows={2} value={topic.learning_objectives} onChange={(event) => updateTopic(sectionIndex, topicIndex, 'learning_objectives', event.target.value)} className={`${fieldClass()} mt-1 resize-y`} /></label>
                        </div>
                      ))}
                      <button type="button" onClick={() => updateSection(sectionIndex, (current) => ({ ...current, topics: [...current.topics, emptyTopic(current.topics.length + 1)] }))} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold text-primary hover:bg-primary/5"><Plus className="h-4 w-4" /> Добавить тему</button>
                    </div>
                  </details>
                ))}
              </section>
              {error && <p role="alert" className="rounded-lg bg-destructive/10 px-4 py-3 text-sm font-semibold text-destructive">{error}</p>}
            </div>
            <DialogFooter className="border-t border-border bg-background px-6 py-4">
              <button type="button" disabled={stage === 'saving'} onClick={reset} className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted disabled:opacity-50">Выбрать другой файл</button>
              <button type="button" disabled={stage === 'saving'} onClick={() => void save()} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
                {stage === 'saving' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{stage === 'saving' ? 'Сохраняем...' : `Импортировать ${summary.topics} тем`}
              </button>
            </DialogFooter>
          </>
        )}

        {stage === 'success' && (
          <div className="flex min-h-80 flex-col items-center justify-center p-8 text-center">
            <CheckCircle2 className="h-14 w-14 text-emerald-500" />
            <h3 className="mt-5 text-2xl font-bold text-foreground">КТП добавлен</h3>
            <p className="mt-2 max-w-lg text-muted-foreground">Разделы и темы появились в курсе. Теперь можно перейти к генерации уроков.</p>
            <div className="mt-6 flex gap-3"><button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted">Закрыть</button><Link href="/dashboard/lessons" onClick={() => setOpen(false)} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground">Открыть темы</Link></div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function KtpImportPanel() {
  const [open, setOpen] = useState(false);
  return (
    <section className="grid gap-6 border-y border-border py-6 md:grid-cols-[1fr_auto] md:items-center">
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><FileSpreadsheet className="h-5 w-5" /></div>
        <div><h2 className="text-lg font-bold text-foreground">Добавить КТП</h2><p className="mt-1 max-w-2xl text-sm text-muted-foreground">Загрузите план по любому предмету для 7–10 классов. Перед импортом вы увидите все разделы, темы и цели.</p></div>
      </div>
      <div className="flex flex-wrap gap-2 md:justify-end">
        <a href={TEMPLATE_URL} download className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted"><Download className="h-4 w-4" /> Шаблон</a>
        <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground hover:bg-primary/90"><FileUp className="h-4 w-4" /> Загрузить КТП</button>
      </div>
      <KtpImportDialog open={open} onOpenChange={setOpen} />
    </section>
  );
}

export function KtpImportButton() {
  const [open, setOpen] = useState(false);
  return <><button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90"><FileUp className="h-4 w-4" /> Загрузить КТП</button><KtpImportDialog open={open} onOpenChange={setOpen} /></>;
}
